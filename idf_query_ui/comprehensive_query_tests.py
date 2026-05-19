#!/usr/bin/env python3
"""
Comprehensive Query Protobuf Test Suite

Tests all possible combinations of Query protobuf fields to ensure
the IDF MCP server handles every scenario correctly.
"""

import requests
import json
import time
from typing import Dict, List, Any

API_URL = "http://localhost:3001/generate"

class QueryTester:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        
    def test_query(self, name: str, query: str, expected_features: Dict[str, Any] = None):
        """Test a single query and validate the output"""
        print(f"\n{'='*80}")
        print(f"TEST: {name}")
        print(f"Query: {query}")
        print(f"{'='*80}")
        
        try:
            response = requests.post(
                API_URL,
                json={"query": query},
                timeout=15
            )
            
            if response.status_code != 200:
                self.failed += 1
                error = f"HTTP {response.status_code}: {response.text[:200]}"
                self.errors.append(f"{name}: {error}")
                print(f"❌ FAILED: {error}")
                return False
            
            data = response.json()
            
            if not data.get('success'):
                self.failed += 1
                error = data.get('error', 'Unknown error')
                self.errors.append(f"{name}: {error}")
                print(f"❌ FAILED: {error}")
                return False
            
            # Validate expected features
            protobuf = data.get('protobuf_json', {})
            
            if expected_features:
                for feature, expected_value in expected_features.items():
                    if feature not in str(protobuf):
                        self.failed += 1
                        error = f"Missing expected feature: {feature}"
                        self.errors.append(f"{name}: {error}")
                        print(f"❌ FAILED: {error}")
                        return False
            
            self.passed += 1
            print(f"✅ PASSED")
            print(f"Protobuf: {json.dumps(protobuf, indent=2)[:500]}...")
            return True
            
        except Exception as e:
            self.failed += 1
            error = str(e)
            self.errors.append(f"{name}: {error}")
            print(f"❌ EXCEPTION: {error}")
            return False
    
    def print_summary(self):
        """Print test summary"""
        print(f"\n{'='*80}")
        print(f"TEST SUMMARY")
        print(f"{'='*80}")
        print(f"Total Tests: {self.passed + self.failed}")
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        
        if self.errors:
            print(f"\n{'='*80}")
            print(f"ERRORS:")
            print(f"{'='*80}")
            for error in self.errors:
                print(f"  • {error}")
        
        print(f"\n{'='*80}")


def main():
    tester = QueryTester()
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                   COMPREHENSIVE QUERY PROTOBUF TEST SUITE                    ║
║                                                                              ║
║  Testing all possible combinations of Query protobuf fields                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
    
    # =========================================================================
    # 1. BASIC ENTITY QUERIES
    # =========================================================================
    print("\n" + "="*80)
    print("SECTION 1: BASIC ENTITY QUERIES")
    print("="*80)
    
    tester.test_query(
        "1.1 - Simple entity fetch",
        "Get all VMs",
        {"entity_type_name": "vm"}
    )
    
    tester.test_query(
        "1.2 - Fetch clusters",
        "Fetch all clusters",
        {"entity_type_name": "cluster"}
    )
    
    tester.test_query(
        "1.3 - Fetch hosts",
        "Get all hosts",
        {"entity_type_name": "host"}
    )
    
    # =========================================================================
    # 2. LIMIT QUERIES
    # =========================================================================
    print("\n" + "="*80)
    print("SECTION 2: LIMIT QUERIES")
    print("="*80)
    
    tester.test_query(
        "2.1 - First N entities",
        "Fetch first 100 VMs",
        {"limit": 100}
    )
    
    tester.test_query(
        "2.2 - Top N entities",
        "Get top 50 clusters",
        {"limit": 50}
    )
    
    tester.test_query(
        "2.3 - Limit with number prefix",
        "Get 25 hosts",
        {"limit": 25}
    )
    
    # =========================================================================
    # 3. WHERE CLAUSE - POWER STATE
    # =========================================================================
    print("\n" + "="*80)
    print("SECTION 3: WHERE CLAUSE - POWER STATE")
    print("="*80)
    
    tester.test_query(
        "3.1 - Powered on VMs",
        "Find all VMs that are powered on",
        {"power_state": "on"}
    )
    
    tester.test_query(
        "3.2 - Powered off VMs",
        "Get VMs that are powered off",
        {"power_state": "off"}
    )
    
    # =========================================================================
    # 4. WHERE CLAUSE - COMPARISONS
    # =========================================================================
    print("\n" + "="*80)
    print("SECTION 4: WHERE CLAUSE - COMPARISONS")
    print("="*80)
    
    tester.test_query(
        "4.1 - Greater than",
        "Get all VMs where cpu_usage_ppm > 500000",
        {"kGT": True, "cpu_usage_ppm": True}
    )
    
    tester.test_query(
        "4.2 - Less than",
        "Fetch VMs where memory_mb < 8192",
        {"kLT": True, "memory_mb": True}
    )
    
    tester.test_query(
        "4.3 - Equals",
        "Get VMs where vm_name equals test-vm",
        {"kEQ": True, "vm_name": True}
    )
    
    tester.test_query(
        "4.4 - Contains",
        "Find VMs whose vm_name contains prod",
        {"kContains": True, "vm_name": True}
    )
    
    # =========================================================================
    # 5. RAW COLUMNS (Column Selection)
    # =========================================================================
    print("\n" + "="*80)
    print("SECTION 5: RAW COLUMNS (Column Selection)")
    print("="*80)
    
    tester.test_query(
        "5.1 - Single column",
        "Fetch all VMs with vm_name",
        {"raw_columns": True, "vm_name": True}
    )
    
    tester.test_query(
        "5.2 - Multiple columns",
        "Get all VMs with vm_name and memory_mb",
        {"raw_columns": True, "vm_name": True, "memory_mb": True}
    )
    
    tester.test_query(
        "5.3 - Three columns",
        "Fetch VMs with vm_name, memory_mb, and cpu_usage_ppm",
        {"raw_columns": True}
    )
    
    # =========================================================================
    # 6. GROUP BY QUERIES
    # =========================================================================
    print("\n" + "="*80)
    print("SECTION 6: GROUP BY QUERIES")
    print("="*80)
    
    tester.test_query(
        "6.1 - Simple group by",
        "Group VMs by cluster_name",
        {"group_by": True, "cluster_name": True}
    )
    
    tester.test_query(
        "6.2 - Group by with raw columns",
        "Group VMs by power_state with vm_name",
        {"group_by": True, "power_state": True, "raw_columns": True}
    )
    
    # =========================================================================
    # 7. AGGREGATION QUERIES
    # =========================================================================
    print("\n" + "="*80)
    print("SECTION 7: AGGREGATION QUERIES")
    print("="*80)
    
    tester.test_query(
        "7.1 - Sum aggregation",
        "Get sum of memory_mb for all VMs",
        {"aggregate_columns": True, "kSum": True, "memory_mb": True}
    )
    
    tester.test_query(
        "7.2 - Average aggregation",
        "Calculate average cpu_usage_ppm for VMs",
        {"aggregate_columns": True, "kAvg": True}
    )
    
    tester.test_query(
        "7.3 - Count query with flags",
        "Count all VMs",
        {"flags": 2}  # Count queries use flags, not aggregate_columns
    )
    
    # =========================================================================
    # 8. COUNT QUERIES (with flags)
    # =========================================================================
    print("\n" + "="*80)
    print("SECTION 8: COUNT QUERIES (with flags)")
    print("="*80)
    
    tester.test_query(
        "8.1 - Count query",
        "How many VMs are there",
        {"flags": 2}
    )
    
    tester.test_query(
        "8.2 - Total number query",
        "What is the total number of clusters",
        {"flags": 2}
    )
    
    # =========================================================================
    # 9. CURSOR QUERIES (Pagination)
    # =========================================================================
    print("\n" + "="*80)
    print("SECTION 9: CURSOR QUERIES (Pagination)")
    print("="*80)
    
    tester.test_query(
        "9.1 - Initial cursor query",
        "Fetch all VMs using a cursor query",
        {"cursor_query_info": True, "is_initial_cursor_query": True}
    )
    
    tester.test_query(
        "9.2 - Cursor with batch size",
        "Get VMs using cursor query with batch size 50",
        {"cursor_query_info": True, "batch_size": 50}
    )
    
    # =========================================================================
    # 10. COMBINED QUERIES
    # =========================================================================
    print("\n" + "="*80)
    print("SECTION 10: COMBINED QUERIES")
    print("="*80)
    
    tester.test_query(
        "10.1 - Limit + Where clause",
        "Get first 100 VMs where cpu_usage_ppm > 500000",
        {"limit": 100, "kGT": True}
    )
    
    tester.test_query(
        "10.2 - Limit + Raw columns",
        "Fetch first 50 VMs with vm_name and memory_mb",
        {"limit": 50, "raw_columns": True}
    )
    
    tester.test_query(
        "10.3 - Where + Raw columns",
        "Get powered on VMs with vm_name and cpu_usage_ppm",
        {"power_state": "on", "raw_columns": True}
    )
    
    tester.test_query(
        "10.4 - Limit + Where + Raw columns",
        "Fetch first 100 powered on VMs with vm_name and memory_mb",
        {"limit": 100, "power_state": "on", "raw_columns": True}
    )
    
    tester.test_query(
        "10.5 - Cursor + Where clause",
        "Get powered on VMs using a cursor query",
        {"cursor_query_info": True, "power_state": "on"}
    )
    
    tester.test_query(
        "10.6 - Cursor + Raw columns",
        "Fetch VMs with vm_name using cursor query",
        {"cursor_query_info": True, "raw_columns": True}
    )
    
    tester.test_query(
        "10.7 - Group by + Aggregation",
        "Group VMs by cluster_name with sum of memory_mb",
        {"group_by": True, "aggregate_columns": True}
    )
    
    tester.test_query(
        "10.8 - Where + Group by",
        "Group powered on VMs by cluster_name",
        {"power_state": "on", "group_by": True}
    )
    
    # =========================================================================
    # 11. COMPLEX COMBINED QUERIES
    # =========================================================================
    print("\n" + "="*80)
    print("SECTION 11: COMPLEX COMBINED QUERIES")
    print("="*80)
    
    tester.test_query(
        "11.1 - All features combined",
        "Get first 100 powered on VMs with vm_name and memory_mb where cpu_usage_ppm > 500000 using a cursor query",
        {"limit": 100, "power_state": "on", "raw_columns": True, "kGT": True, "cursor_query_info": True}
    )
    
    tester.test_query(
        "11.2 - Multiple where conditions",
        "Get VMs where cpu_usage_ppm > 500000 and memory_mb > 8192",
        {"kGT": True, "cpu_usage_ppm": True, "memory_mb": True}
    )
    
    # =========================================================================
    # 12. EDGE CASES
    # =========================================================================
    print("\n" + "="*80)
    print("SECTION 12: EDGE CASES")
    print("="*80)
    
    tester.test_query(
        "12.1 - Very large limit",
        "Fetch first 10000 VMs",
        {"limit": 10000}
    )
    
    tester.test_query(
        "12.2 - Limit of 1",
        "Get first 1 VM",
        {"limit": 1}
    )
    
    tester.test_query(
        "12.3 - Multiple entity types (should pick one)",
        "Get all VMs and clusters",
        {}  # Should default to one entity type
    )
    
    # Print final summary
    tester.print_summary()
    
    return tester.passed, tester.failed


if __name__ == "__main__":
    passed, failed = main()
    exit(0 if failed == 0 else 1)
