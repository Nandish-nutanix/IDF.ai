"""
Run validation of LLM-first pipeline against generated questions.

Sends each question to the server and validates:
1. API method matches expected
2. Proto contains all required keywords

Outputs summary with pass/fail rates per category and API.
"""

import json
import os
import sys
import time
import requests
from collections import defaultdict

SERVER_URL = "http://localhost:8000/query"
QUESTIONS_FILE = os.path.join(os.path.dirname(__file__), "validation_questions.json")
RESULTS_FILE = os.path.join(os.path.dirname(__file__), "validation_results.json")

# Only validate API classification (not proto content) for these categories
# since proto keywords depend heavily on exact LLM output
API_ONLY_CATEGORIES = {
    "robustness", "conversational", "tricky_phrasings", "scenarios",
    "comparison_natural", "sorting_natural", "aggregation_natural",
    "natural_language_extended", "specific_patterns", "derived_metrics",
    "action_phrasings",
}


def load_questions():
    with open(QUESTIONS_FILE, "r") as f:
        return json.load(f)


def validate_one(question, timeout=90):
    """Send query to server and validate response."""
    query = question["query"]
    expected_api = question["expected_api"]
    proto_must_have = question.get("proto_must_have", [])
    category = question.get("category", "")

    try:
        t0 = time.time()
        resp = requests.post(SERVER_URL, json={"query": query, "generate_python": False}, timeout=timeout)
        elapsed = time.time() - t0

        if resp.status_code != 200:
            return {
                "status": "error",
                "error": f"HTTP {resp.status_code}: {resp.text[:100]}",
                "elapsed": elapsed,
            }

        data = resp.json()
        api_method = data.get("api_method", "")
        proto = data.get("query_proto", "")

        issues = []

        # Check API method
        if api_method != expected_api:
            issues.append(f"api={api_method} (expected {expected_api})")

        # Check proto keywords (skip for natural language categories)
        if category not in API_ONLY_CATEGORIES and proto_must_have:
            for kw in proto_must_have:
                if kw and kw not in proto:
                    issues.append(f"proto missing '{kw}'")
                    break

        return {
            "status": "fail" if issues else "pass",
            "issues": issues,
            "api_method": api_method,
            "elapsed": elapsed,
            "proto_snippet": proto[:200],
        }

    except requests.exceptions.Timeout:
        return {"status": "error", "error": "timeout", "elapsed": timeout}
    except Exception as e:
        return {"status": "error", "error": str(e), "elapsed": 0}


def run_batch(questions, batch_size=50, start_idx=0):
    """Run validation in batches with progress reporting."""
    results = []
    total = len(questions)

    for i in range(start_idx, total):
        q = questions[i]
        qid = q["id"]
        query_short = q["query"][:50]
        category = q.get("category", "")

        result = validate_one(q)
        result["id"] = qid
        result["query"] = q["query"]
        result["expected_api"] = q["expected_api"]
        result["category"] = category
        results.append(result)

        status_sym = "PASS" if result["status"] == "pass" else "FAIL" if result["status"] == "fail" else "ERR "
        elapsed_str = f"{result['elapsed']:.1f}s"
        print(f"[{qid}] {status_sym} [{elapsed_str}] {query_short}")

        if result["status"] == "fail":
            for issue in result.get("issues", []):
                print(f"       -> {issue}")

        sys.stdout.flush()

        # Progress report every batch_size
        if (i + 1) % batch_size == 0:
            passed = sum(1 for r in results if r["status"] == "pass")
            failed = sum(1 for r in results if r["status"] == "fail")
            errors = sum(1 for r in results if r["status"] == "error")
            print(f"\n--- Progress: {i+1}/{total} | Pass: {passed} | Fail: {failed} | Error: {errors} ---\n")
            sys.stdout.flush()

    return results


def print_summary(results):
    """Print detailed summary of validation results."""
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    errors = sum(1 for r in results if r["status"] == "error")

    print("\n" + "=" * 70)
    print(f"VALIDATION RESULTS: {passed}/{total} PASS ({passed/total*100:.1f}%)")
    print(f"  Passed: {passed} | Failed: {failed} | Errors: {errors}")
    print("=" * 70)

    # Per-API breakdown
    api_stats = defaultdict(lambda: {"pass": 0, "fail": 0, "error": 0, "total": 0})
    for r in results:
        api = r["expected_api"]
        api_stats[api][r["status"]] += 1
        api_stats[api]["total"] += 1

    print("\nPer-API Accuracy:")
    print(f"{'API':<35} {'Pass':>5} {'Fail':>5} {'Err':>5} {'Total':>5} {'Rate':>7}")
    print("-" * 70)
    for api in sorted(api_stats.keys()):
        s = api_stats[api]
        rate = s["pass"] / s["total"] * 100 if s["total"] > 0 else 0
        print(f"{api:<35} {s['pass']:>5} {s['fail']:>5} {s['error']:>5} {s['total']:>5} {rate:>6.1f}%")

    # Per-category breakdown
    cat_stats = defaultdict(lambda: {"pass": 0, "fail": 0, "error": 0, "total": 0})
    for r in results:
        cat = r.get("category", "unknown")
        cat_stats[cat][r["status"]] += 1
        cat_stats[cat]["total"] += 1

    print("\nPer-Category Accuracy (showing categories with failures):")
    print(f"{'Category':<35} {'Pass':>5} {'Fail':>5} {'Rate':>7}")
    print("-" * 55)
    for cat in sorted(cat_stats.keys(), key=lambda x: cat_stats[x]["fail"], reverse=True):
        s = cat_stats[cat]
        if s["fail"] > 0 or s["error"] > 0:
            rate = s["pass"] / s["total"] * 100 if s["total"] > 0 else 0
            print(f"{cat:<35} {s['pass']:>5} {s['fail']:>5} {rate:>6.1f}%")

    # Show failure details
    failures = [r for r in results if r["status"] == "fail"]
    if failures:
        print("\n--- Top Failures (showing first 30) ---")
        for r in failures[:30]:
            print(f"  [{r['id']}] {r['query'][:60]}")
            for issue in r.get("issues", []):
                print(f"         -> {issue}")

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "accuracy_pct": round(passed / total * 100, 1),
        "api_stats": dict(api_stats),
        "cat_stats": dict(cat_stats),
    }


def main():
    # Parse args
    start_idx = 0
    max_count = None
    for arg in sys.argv[1:]:
        if arg.startswith("--start="):
            start_idx = int(arg.split("=")[1])
        elif arg.startswith("--count="):
            max_count = int(arg.split("=")[1])

    print("=" * 70)
    print("LLM-FIRST VALIDATION RUNNER")
    print("=" * 70)

    questions = load_questions()
    print(f"Loaded {len(questions)} questions from {QUESTIONS_FILE}")

    if max_count:
        questions = questions[start_idx:start_idx + max_count]
        print(f"Running subset: start={start_idx}, count={max_count}")
    elif start_idx > 0:
        questions = questions[start_idx:]
        print(f"Running from index {start_idx}")

    # Verify server is up
    try:
        r = requests.get("http://localhost:8000/", timeout=5)
        if r.status_code != 200:
            print("ERROR: Server not responding properly")
            sys.exit(1)
        print(f"Server OK: {r.json().get('architecture', 'unknown')} architecture")
    except Exception as e:
        print(f"ERROR: Cannot reach server at localhost:8000: {e}")
        sys.exit(1)

    print(f"\nStarting validation of {len(questions)} questions...\n")

    results = run_batch(questions)
    summary = print_summary(results)

    # Save results
    with open(RESULTS_FILE, "w") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2)
    print(f"\nResults saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
