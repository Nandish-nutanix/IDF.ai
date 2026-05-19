"""
Validation script for the improved IDF query pipeline.
Tests query classification, template generation, and proto structure
against 15+ real-world query patterns.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import query_classifier
from proto_response_generator import validate_proto_structure, _ensure_query_wrapper


TEST_QUERIES = [
    {
        "nl": "get all VMs",
        "expected_type": "simple_fetch_all",
        "expected_entity": "vm",
        "must_contain": ['entity_type_name: "vm"', 'query_name:'],
        "must_not_contain": ["where_clause"],
    },
    {
        "nl": "count all disks",
        "expected_type": "count",
        "expected_entity": "disk",
        "must_contain": ['entity_type_name: "disk"', 'flags: 2', 'query_name:'],
    },
    {
        "nl": "VMs with num_vcpus = 4",
        "expected_type": "filter_equality",
        "expected_entity": "vm",
        "must_contain": ['entity_type_name: "vm"', 'where_clause', 'operator: kEQ',
                         'column: "num_vcpus"', 'query_name:'],
    },
    {
        "nl": "VMs where cpu_usage > 80",
        "expected_type": "filter_comparison",
        "expected_entity": "vm",
        "must_contain": ['entity_type_name: "vm"', 'where_clause', 'operator: kGT',
                         'column: "cpu_usage"', '80', 'query_name:'],
    },
    {
        "nl": "VMs where memory_usage >= 60",
        "expected_type": "filter_comparison",
        "expected_entity": "vm",
        "must_contain": ['entity_type_name: "vm"', 'where_clause', 'operator: kGE',
                         'column: "memory_usage"', '60'],
    },
    {
        "nl": "top 5 VMs sorted by memory descending",
        "expected_type": "sort_limit",
        "expected_entity": "vm",
        "must_contain": ['entity_type_name: "vm"', 'raw_limit', 'limit: 5',
                         'sort_column: "memory"', 'kDescending'],
    },
    {
        "nl": "group VMs by cluster",
        "expected_type": "group_by",
        "expected_entity": "vm",
        "must_contain": ['entity_type_name: "vm"', 'group_by_column: "cluster"', 'query_name:'],
    },
    {
        "nl": "how many VMs are there",
        "expected_type": "count",
        "expected_entity": "vm",
        "must_contain": ['entity_type_name: "vm"', 'flags: 2'],
    },
    {
        "nl": "average memory_usage_bytes grouped by vm_name",
        "expected_type": "aggregation",
        "expected_entity": "vm",
        "must_contain": ['entity_type_name: "vm"'],
    },
    {
        "nl": "latest 100 tasks",
        "expected_type": "sort_limit",
        "expected_entity": "task",
        "must_contain": ['entity_type_name: "task"', 'raw_limit', 'limit: 100'],
    },
    {
        "nl": "VMs belonging to cluster abc-123-def",
        "expected_type": "filter_equality",
        "expected_entity": "vm",
        "must_contain": ['entity_type_name: "vm"', 'where_clause',
                         'cluster_uuid', 'abc-123-def'],
    },
    {
        "nl": "alerts where severity exists",
        "expected_type": "filter_equality",
        "expected_entity": "alert",
        "must_contain": ['entity_type_name: "alert"', 'where_clause', 'kExists',
                         'column: "severity"'],
        "must_not_contain": ["rhs"],
    },
    {
        "nl": "number of clusters",
        "expected_type": "count",
        "expected_entity": "cluster",
        "must_contain": ['entity_type_name: "cluster"', 'flags: 2'],
    },
    {
        "nl": "VMs with power_state = ON sorted by vm_name ascending",
        "expected_type": "filter_equality",
        "expected_entity": "vm",
        "must_contain": ['entity_type_name: "vm"', 'where_clause', 'kEQ',
                         'power_state'],
    },
    {
        "nl": "first 10 hosts",
        "expected_type": "sort_limit",
        "expected_entity": "host",
        "must_contain": ['entity_type_name: "host"', 'raw_limit', 'limit: 10'],
    },
]


def run_tests():
    """Run all validation tests."""
    passed = 0
    failed = 0
    total = len(TEST_QUERIES)

    print(f"Running {total} query accuracy tests...\n")
    print("=" * 70)

    for i, test in enumerate(TEST_QUERIES, 1):
        nl = test["nl"]
        expected_type = test["expected_type"]
        expected_entity = test.get("expected_entity")
        must_contain = test.get("must_contain", [])
        must_not_contain = test.get("must_not_contain", [])

        classified = query_classifier.classify_query(nl)

        errors = []

        # Check query type
        if classified.query_type.value != expected_type:
            errors.append(f"  Type: expected '{expected_type}', got '{classified.query_type.value}'")

        # Check entity type
        if expected_entity and classified.entity_type != expected_entity:
            errors.append(f"  Entity: expected '{expected_entity}', got '{classified.entity_type}'")

        # Try template generation
        proto = None
        if classified.can_use_template:
            proto = query_classifier.generate_template_proto(classified)

        if proto:
            # Validate structure
            is_valid, error = validate_proto_structure(proto)
            if not is_valid:
                errors.append(f"  Validation failed: {error}")

            # Check query { } wrapper
            if not proto.strip().startswith("query {"):
                errors.append("  Missing query { } wrapper")

            # Check must_contain
            for pattern in must_contain:
                if pattern not in proto:
                    errors.append(f"  Missing in proto: '{pattern}'")

            # Check must_not_contain
            for pattern in must_not_contain:
                if pattern in proto:
                    errors.append(f"  Should NOT contain: '{pattern}'")
        else:
            # For non-template queries, just check classification is correct
            if classified.can_use_template:
                errors.append("  Template generation returned None despite can_use_template=True")

        # Report
        status = "PASS" if not errors else "FAIL"
        if errors:
            failed += 1
            print(f"[{status}] Test {i}: \"{nl}\"")
            for err in errors:
                print(err)
            if proto:
                print(f"  Generated proto (first 200 chars):")
                print(f"    {proto[:200]}")
            print()
        else:
            passed += 1
            print(f"[{status}] Test {i}: \"{nl}\" -> {classified.query_type.value} (conf={classified.confidence:.2f}, template={'yes' if proto else 'no'})")

    print("=" * 70)
    print(f"\nResults: {passed}/{total} passed, {failed}/{total} failed")

    if failed == 0:
        print("\nAll tests passed!")
    else:
        print(f"\n{failed} tests need attention.")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
