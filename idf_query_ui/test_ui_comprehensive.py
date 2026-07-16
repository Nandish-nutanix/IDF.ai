#!/usr/bin/env python3
"""
Comprehensive UI Testing Script
Tests both simple and complex queries through the UI backend
"""

import requests
import json
import time
from typing import Dict, Any

# Backend URL
BACKEND_URL = "http://localhost:3001"

# Test queries organized by complexity and type
TEST_QUERIES = {
    "simple_fetch": [
        "Get all VMs",
        "Fetch all clusters",
        "List all hosts",
        "Show all containers",
        "Retrieve all virtual disks",
    ],
    
    "fetch_with_columns": [
        "Get all VMs with vm_name",
        "Fetch all clusters with cluster_name",
        "Get VMs with vm_name and memory_mb",
        "Fetch clusters with cluster_name, node_count, and storage_capacity",
        "Get hosts with host_name and ip_address",
    ],
    
    "where_clause_simple": [
        "Get all VMs where vm_name equals test-vm",
        "Fetch VMs whose vm_name contains prod",
        "Get clusters where cluster_name equals main-cluster",
        "Fetch hosts whose host_name contains node",
    ],
    
    "where_clause_numeric": [
        "Get all VMs where cpu_usage_ppm greater than 500000",
        "Fetch VMs whose memory_mb > 4096",
        "Get clusters where node_count >= 3",
        "Fetch VMs where cpu_usage_ppm < 100000",
        "Get hosts whose memory_capacity_bytes greater than 1000000000",
    ],
    
    "cursor_queries": [
        "Fetch all VMs using a cursor query",
        "Get all clusters with cluster_name using pagination",
        "Fetch VMs with vm_name using cursor query with batch size 50",
        "Get hosts with host_name using a cursor",
    ],
    
    "grouping_queries": [
        "Get all VMs grouped by cluster_uuid",
        "Fetch containers grouped by node_uuid",
        "Get virtual disks grouped by storage_tier",
        "Fetch VMs grouped by host_uuid",
    ],
    
    "count_queries": [
        "Count all VMs",
        "How many clusters are there",
        "Total number of hosts",
        "Count VMs where cpu_usage_ppm > 500000",
        "How many VMs are in cluster xyz",
    ],
    
    "aggregation_queries": [
        "Get sum of memory_mb for all VMs",
        "Fetch average cpu_usage_ppm for VMs",
        "Get total memory_mb grouped by cluster_uuid",
        "Fetch sum of storage_capacity for clusters",
    ],
    
    "complex_queries": [
        "Get all VMs with vm_name and memory_mb where cpu_usage_ppm > 500000 using a cursor query",
        "Fetch VMs grouped by cluster_uuid with sum of memory_mb",
        "Get all clusters with cluster_name where node_count >= 3 using pagination",
        "Fetch VMs with vm_name, memory_mb, and cpu_usage_ppm where vm_name contains prod using cursor",
        "Count all VMs grouped by host_uuid where memory_mb > 4096",
    ],
    
    "edge_cases": [
        "Get VMs",  # Minimal query
        "Fetch all clusters with cluster_name using a cursor query",  # Previously broken
        "Get VMs with vm_name, memory_mb, and cpu_usage_ppm",  # Oxford comma
        "Fetch entities of type vm",  # Different phrasing
        "Show me all the virtual machines",  # Natural language
    ],
    
    "update_delete": [
        "Update entity vm with id abc123",
        "Delete entity cluster with id xyz789",
        "Create entity vm with vm_name test-vm",
    ],
}


def test_query(query: str, category: str) -> Dict[str, Any]:
    """Test a single query through the UI backend"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/generate",
            json={"query": query},
            timeout=30
        )
        
        result = {
            "query": query,
            "category": category,
            "status": "success" if response.status_code == 200 else "failed",
            "status_code": response.status_code,
            "response_time_ms": int(response.elapsed.total_seconds() * 1000),
        }
        
        if response.status_code == 200:
            data = response.json()
            result["entity_type"] = data.get("entity_type")
            result["rpc"] = data.get("rpc")
            result["confidence"] = data.get("confidence")
            result["has_protobuf"] = bool(data.get("protobuf_json"))
            result["has_python"] = bool(data.get("python_code"))
            
            # Validate protobuf structure
            protobuf = data.get("protobuf_json", {})
            if protobuf:
                result["validation"] = validate_protobuf(protobuf, query)
            
        else:
            result["error"] = response.text
            
        return result
        
    except Exception as e:
        return {
            "query": query,
            "category": category,
            "status": "error",
            "error": str(e)
        }


def validate_protobuf(protobuf: Dict, query: str) -> Dict[str, Any]:
    """Validate the generated protobuf structure"""
    issues = []
    warnings = []
    
    # Check basic structure
    if "query" not in protobuf:
        issues.append("Missing 'query' field")
        return {"issues": issues, "warnings": warnings}
    
    query_obj = protobuf["query"]
    
    # Check entity_list
    if "entity_list" not in query_obj:
        issues.append("Missing 'entity_list'")
    elif not query_obj["entity_list"]:
        warnings.append("Empty entity_list")
    
    # Check for raw_columns issues
    if "group_by" in query_obj and "raw_columns" in query_obj["group_by"]:
        raw_cols = query_obj["group_by"]["raw_columns"]
        for col in raw_cols:
            col_name = col.get("column", "")
            # Check if column name contains keywords that shouldn't be there
            if any(keyword in col_name.lower() for keyword in ["using", "where", "order by", "limit", "with"]):
                issues.append(f"Column name contains keyword: '{col_name}'")
            # Check if column name has spaces (usually wrong)
            if " " in col_name and col_name not in ["entity_id", "vm_name"]:
                warnings.append(f"Column name has spaces: '{col_name}'")
    
    # Check cursor query
    if "cursor" in query.lower() or "pagination" in query.lower():
        if "cursor_query_info" not in protobuf:
            warnings.append("Query mentions cursor but no cursor_query_info")
    
    # Check count query
    if any(word in query.lower() for word in ["count", "how many", "total number"]):
        if query_obj.get("flags") != 2:
            warnings.append("Count query but flags != 2")
    
    # Check where clause
    if any(word in query.lower() for word in ["where", "whose"]):
        if "where_clause" not in query_obj:
            warnings.append("Query mentions where but no where_clause")
    
    # Check grouping
    if "grouped by" in query.lower() or "group by" in query.lower():
        if "group_by" not in query_obj:
            warnings.append("Query mentions grouping but no group_by")
        elif "group_by_column" not in query_obj["group_by"]:
            warnings.append("group_by exists but no group_by_column")
    
    return {
        "issues": issues,
        "warnings": warnings,
        "is_valid": len(issues) == 0
    }


def print_category_header(category: str):
    """Print a formatted category header"""
    print(f"\n{'='*80}")
    print(f"  {category.upper().replace('_', ' ')}")
    print(f"{'='*80}")


def print_result(result: Dict[str, Any], index: int):
    """Print a formatted test result"""
    status_emoji = "✅" if result["status"] == "success" else "❌"
    
    print(f"\n{index}. {status_emoji} {result['query']}")
    print(f"   Status: {result['status']} ({result.get('response_time_ms', 0)}ms)")
    
    if result["status"] == "success":
        entity = result.get('entity_type', 'N/A')
        rpc = result.get('rpc', 'N/A')
        confidence = result.get('confidence', 0.0)
        if confidence is None:
            confidence = 0.0
        print(f"   Entity: {entity} | RPC: {rpc} | Confidence: {confidence:.2f}")
        
        if "validation" in result:
            validation = result["validation"]
            if validation.get("issues"):
                print(f"   🐛 ISSUES: {', '.join(validation['issues'])}")
            if validation.get("warnings"):
                print(f"   ⚠️  WARNINGS: {', '.join(validation['warnings'])}")
            if validation.get("is_valid", True) and not validation.get("warnings"):
                print("   ✅ Validation: PASSED")
    else:
        print(f"   Error: {result.get('error', 'Unknown error')}")


def run_tests():
    """Run all tests and generate report"""
    print("\n" + "="*80)
    print("  IDF QUERY UI - COMPREHENSIVE TEST SUITE")
    print("="*80)
    print(f"  Backend: {BACKEND_URL}")
    print(f"  Total Categories: {len(TEST_QUERIES)}")
    print(f"  Total Queries: {sum(len(queries) for queries in TEST_QUERIES.values())}")
    print("="*80)
    
    all_results = []
    category_stats = {}
    
    for category, queries in TEST_QUERIES.items():
        print_category_header(category)
        
        category_results = []
        for i, query in enumerate(queries, 1):
            result = test_query(query, category)
            category_results.append(result)
            all_results.append(result)
            print_result(result, i)
            time.sleep(0.5)  # Rate limiting
        
        # Category statistics
        success_count = sum(1 for r in category_results if r["status"] == "success")
        issue_count = sum(1 for r in category_results if r.get("validation", {}).get("issues"))
        warning_count = sum(1 for r in category_results if r.get("validation", {}).get("warnings"))
        
        category_stats[category] = {
            "total": len(queries),
            "success": success_count,
            "issues": issue_count,
            "warnings": warning_count,
            "success_rate": (success_count / len(queries)) * 100
        }
    
    # Final report
    print("\n" + "="*80)
    print("  FINAL REPORT")
    print("="*80)
    
    total_tests = len(all_results)
    total_success = sum(1 for r in all_results if r["status"] == "success")
    total_issues = sum(1 for r in all_results if r.get("validation", {}).get("issues"))
    total_warnings = sum(1 for r in all_results if r.get("validation", {}).get("warnings"))
    
    print("\n📊 Overall Statistics:")
    print(f"   Total Tests: {total_tests}")
    print(f"   Successful: {total_success} ({(total_success/total_tests)*100:.1f}%)")
    print(f"   With Issues: {total_issues}")
    print(f"   With Warnings: {total_warnings}")
    
    print("\n📈 Category Breakdown:")
    for category, stats in category_stats.items():
        status = "✅" if stats["success_rate"] == 100 and stats["issues"] == 0 else "⚠️" if stats["success_rate"] >= 80 else "❌"
        print(f"   {status} {category:25s}: {stats['success']}/{stats['total']} success, {stats['issues']} issues, {stats['warnings']} warnings")
    
    # List all issues
    issues_found = []
    for result in all_results:
        if result.get("validation", {}).get("issues"):
            issues_found.append({
                "query": result["query"],
                "issues": result["validation"]["issues"]
            })
    
    if issues_found:
        print("\n🐛 ISSUES REQUIRING FIXES:")
        for i, item in enumerate(issues_found, 1):
            print(f"\n   {i}. Query: {item['query']}")
            for issue in item["issues"]:
                print(f"      - {issue}")
    else:
        print("\n✅ NO CRITICAL ISSUES FOUND!")
    
    # Save detailed results
    with open("/Users/kumar.gaurav/Documents/workspace/main/idf_query_ui/test_results.json", "w") as f:
        json.dump({
            "summary": {
                "total_tests": total_tests,
                "total_success": total_success,
                "total_issues": total_issues,
                "total_warnings": total_warnings,
                "success_rate": (total_success/total_tests)*100
            },
            "category_stats": category_stats,
            "all_results": all_results,
            "issues": issues_found
        }, f, indent=2)
    
    print("\n💾 Detailed results saved to: test_results.json")
    print("="*80 + "\n")
    
    return all_results, issues_found


if __name__ == "__main__":
    try:
        # Check if backend is running
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ Backend not healthy: {response.status_code}")
            exit(1)
    except Exception as e:
        print(f"❌ Cannot connect to backend at {BACKEND_URL}")
        print(f"   Error: {e}")
        print("\n   Please ensure the backend is running:")
        print("   cd idf_query_ui/backend && python3 app.py")
        exit(1)
    
    results, issues = run_tests()
    
    # Exit with error code if there are issues
    exit(1 if issues else 0)
