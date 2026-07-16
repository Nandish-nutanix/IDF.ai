#!/usr/bin/env python3
"""
Extensive Language Pattern Test Suite

Tests 100+ queries with different language patterns, raw English,
casual language, and validates that only valid attributes are used.
"""

import requests
from typing import Dict

API_URL = "http://localhost:3001/generate"

# Known valid attributes for different entity types
VALID_ATTRIBUTES = {
    'vm': [
        'vm_name', 'power_state', 'cpu_usage_ppm', 'memory_mb', 'memory_usage_ppm',
        'num_vcpus', 'cluster_uuid', 'host_uuid', 'hypervisor_type', 'ip_addresses',
        'vm_type', 'protection_type', 'protection_domain_name', 'disk_capacity_bytes',
        'controller_avg_io_latency_usecs', 'controller_num_iops', 'controller_avg_read_io_latency_usecs',
        'controller_avg_write_io_latency_usecs', 'hypervisor_cpu_usage_ppm', 'hypervisor_memory_usage_ppm'
    ],
    'cluster': [
        'cluster_name', 'cluster_uuid', 'num_nodes', 'hypervisor_types', 'cluster_external_ipaddress',
        'cluster_external_data_services_ipaddress', 'cluster_fully_qualified_domain_name',
        'storage_capacity_bytes', 'storage_usage_bytes', 'cluster_redundancy_factor'
    ],
    'host': [
        'host_name', 'host_uuid', 'hypervisor_type', 'cpu_capacity_hz', 'memory_capacity_bytes',
        'num_cpu_cores', 'num_cpu_threads', 'cpu_usage_ppm', 'memory_usage_ppm',
        'host_type', 'cluster_uuid', 'serial_number'
    ],
    'container': [
        'container_name', 'container_uuid', 'storage_pool_uuid', 'max_capacity_bytes',
        'replication_factor', 'compression_enabled', 'compression_delay_secs',
        'on_disk_dedup', 'erasure_code', 'erasure_code_delay_secs'
    ]
}

class LanguageTester:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.invalid_attributes = []
        
    def validate_attributes(self, protobuf: Dict, entity_type: str) -> bool:
        """Check if generated attributes are valid"""
        valid_attrs = VALID_ATTRIBUTES.get(entity_type, [])
        
        # Check raw_columns
        if 'query' in protobuf and 'group_by' in protobuf['query']:
            raw_columns = protobuf['query']['group_by'].get('raw_columns', [])
            for col in raw_columns:
                col_name = col.get('column', '')
                if col_name and col_name not in valid_attrs and not col_name.startswith('_'):
                    self.invalid_attributes.append(f"{entity_type}.{col_name}")
                    return False
        
        # Check where clause columns
        if 'query' in protobuf and 'where_clause' in protobuf['query']:
            where = protobuf['query']['where_clause']
            if 'comparison_expr' in where:
                comp = where['comparison_expr']
                if 'lhs' in comp and 'leaf' in comp['lhs']:
                    col_name = comp['lhs']['leaf'].get('column', '')
                    if col_name and col_name not in valid_attrs and col_name not in ['power_state']:
                        self.invalid_attributes.append(f"{entity_type}.{col_name}")
                        return False
        
        return True
    
    def test_query(self, name: str, query: str, category: str = "General"):
        """Test a single query"""
        try:
            response = requests.post(API_URL, json={"query": query}, timeout=15)
            
            if response.status_code != 200:
                self.failed += 1
                self.errors.append(f"{name}: HTTP {response.status_code}")
                print(f"❌ {name}")
                return False
            
            data = response.json()
            
            if not data.get('success'):
                self.failed += 1
                self.errors.append(f"{name}: {data.get('error', 'Unknown')}")
                print(f"❌ {name}")
                return False
            
            # Validate attributes
            protobuf = data.get('protobuf_json', {})
            entity_type = data.get('entity_type', 'vm')
            
            if not self.validate_attributes(protobuf, entity_type):
                self.failed += 1
                print(f"❌ {name} - Invalid attributes")
                return False
            
            self.passed += 1
            print(f"✅ {name}")
            return True
            
        except Exception as e:
            self.failed += 1
            self.errors.append(f"{name}: {str(e)}")
            print(f"❌ {name} - Exception")
            return False
    
    def print_summary(self):
        """Print test summary"""
        print(f"\n{'='*80}")
        print("TEST SUMMARY")
        print(f"{'='*80}")
        print(f"Total Tests: {self.passed + self.failed}")
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"Success Rate: {(self.passed / (self.passed + self.failed) * 100):.1f}%")
        
        if self.invalid_attributes:
            print(f"\n{'='*80}")
            print("INVALID ATTRIBUTES DETECTED:")
            print(f"{'='*80}")
            for attr in set(self.invalid_attributes):
                print(f"  • {attr}")
        
        if self.errors:
            print(f"\n{'='*80}")
            print("ERRORS (showing first 10):")
            print(f"{'='*80}")
            for error in self.errors[:10]:
                print(f"  • {error}")


def main():
    tester = LanguageTester()
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║              EXTENSIVE LANGUAGE PATTERN TEST SUITE (100+ Queries)            ║
║                                                                              ║
║  Testing different language patterns, raw English, casual language           ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")
    
    # =========================================================================
    # CATEGORY 1: CASUAL/INFORMAL ENGLISH (20 queries)
    # =========================================================================
    print("\n" + "="*80)
    print("CATEGORY 1: CASUAL/INFORMAL ENGLISH (20 queries)")
    print("="*80)
    
    casual_queries = [
        "gimme all vms",
        "show me vms",
        "i want all clusters",
        "can you get me hosts",
        "list out all vms please",
        "fetch me some vms",
        "get all the vms",
        "show all vms",
        "i need vms",
        "give me vms",
        "wanna see all clusters",
        "lemme see hosts",
        "show vms pls",
        "get vms for me",
        "i want to see all vms",
        "can u show vms",
        "pls get vms",
        "need all clusters",
        "want all hosts",
        "show me all the vms"
    ]
    
    for i, query in enumerate(casual_queries, 1):
        tester.test_query(f"Casual-{i}", query, "Casual")
    
    # =========================================================================
    # CATEGORY 2: BROKEN/RAW ENGLISH (20 queries)
    # =========================================================================
    print("\n" + "="*80)
    print("CATEGORY 2: BROKEN/RAW ENGLISH (20 queries)")
    print("="*80)
    
    broken_queries = [
        "get vm all",
        "fetch cluster all",
        "vm get all",
        "all vm fetch",
        "show vm list",
        "vm powered on get",
        "cpu high vm get",
        "memory big vm show",
        "vm name get",
        "cluster name show",
        "vm cpu usage high",
        "get vm memory big",
        "show cluster many vm",
        "vm power on find",
        "host cpu usage show",
        "vm group cluster",
        "count vm all",
        "vm first 100 get",
        "show vm top 50",
        "vm where cpu high"
    ]
    
    for i, query in enumerate(broken_queries, 1):
        tester.test_query(f"Broken-{i}", query, "Broken")
    
    # =========================================================================
    # CATEGORY 3: DIFFERENT VERB FORMS (15 queries)
    # =========================================================================
    print("\n" + "="*80)
    print("CATEGORY 3: DIFFERENT VERB FORMS (15 queries)")
    print("="*80)
    
    verb_queries = [
        "getting all vms",
        "fetching clusters",
        "retrieving hosts",
        "listing vms",
        "showing clusters",
        "displaying hosts",
        "pulling vms",
        "extracting clusters",
        "collecting hosts",
        "gathering vms",
        "obtaining clusters",
        "acquiring hosts",
        "selecting vms",
        "querying clusters",
        "finding hosts"
    ]
    
    for i, query in enumerate(verb_queries, 1):
        tester.test_query(f"Verb-{i}", query, "Verb")
    
    # =========================================================================
    # CATEGORY 4: QUESTIONS (15 queries)
    # =========================================================================
    print("\n" + "="*80)
    print("CATEGORY 4: QUESTIONS (15 queries)")
    print("="*80)
    
    question_queries = [
        "what are all the vms",
        "which vms are powered on",
        "how many vms are there",
        "can you show me clusters",
        "what vms have high cpu",
        "which clusters have vms",
        "how do i get all hosts",
        "what are the powered on vms",
        "which vms use most memory",
        "how many clusters exist",
        "what hosts are available",
        "which vms are in cluster",
        "how to get vm names",
        "what are vm power states",
        "which vms have cpu over 50"
    ]
    
    for i, query in enumerate(question_queries, 1):
        tester.test_query(f"Question-{i}", query, "Question")
    
    # =========================================================================
    # CATEGORY 5: WITH TYPOS (10 queries)
    # =========================================================================
    print("\n" + "="*80)
    print("CATEGORY 5: WITH TYPOS (10 queries)")
    print("="*80)
    
    typo_queries = [
        "get all vms plz",
        "fetch clustrs",
        "show me hsts",
        "get vms pwered on",
        "fetch vm with high cpu usge",
        "show clustr names",
        "get vm memry usage",
        "fetch host cpu uage",
        "show vms in clustr",
        "get vm pwr state"
    ]
    
    for i, query in enumerate(typo_queries, 1):
        tester.test_query(f"Typo-{i}", query, "Typo")
    
    # =========================================================================
    # CATEGORY 6: MIXED CASE (10 queries)
    # =========================================================================
    print("\n" + "="*80)
    print("CATEGORY 6: MIXED CASE (10 queries)")
    print("="*80)
    
    case_queries = [
        "GET ALL VMS",
        "Fetch All Clusters",
        "SHOW ME HOSTS",
        "Get Vms Powered On",
        "FETCH CLUSTERS WITH VMS",
        "Show Hosts In Cluster",
        "GET VM NAMES",
        "Fetch Cluster Names",
        "SHOW VMS WITH HIGH CPU",
        "Get First 100 Vms"
    ]
    
    for i, query in enumerate(case_queries, 1):
        tester.test_query(f"Case-{i}", query, "Case")
    
    # =========================================================================
    # CATEGORY 7: WITH EXTRA WORDS (10 queries)
    # =========================================================================
    print("\n" + "="*80)
    print("CATEGORY 7: WITH EXTRA WORDS (10 queries)")
    print("="*80)
    
    extra_queries = [
        "please get me all the vms now",
        "can you fetch all clusters for me",
        "i would like to see all hosts",
        "kindly show me all vms",
        "please fetch clusters with vms",
        "could you get hosts for me",
        "i want to see all vm names",
        "please show cluster names",
        "can you get vms with high cpu",
        "i need first 100 vms please"
    ]
    
    for i, query in enumerate(extra_queries, 1):
        tester.test_query(f"Extra-{i}", query, "Extra")
    
    # =========================================================================
    # CATEGORY 8: SHORT FORMS (5 queries)
    # =========================================================================
    print("\n" + "="*80)
    print("CATEGORY 8: SHORT FORMS (5 queries)")
    print("="*80)
    
    short_queries = [
        "vms",
        "all vms",
        "clusters",
        "hosts",
        "vm list"
    ]
    
    for i, query in enumerate(short_queries, 1):
        tester.test_query(f"Short-{i}", query, "Short")
    
    # =========================================================================
    # CATEGORY 9: WITH VALID ATTRIBUTES (10 queries)
    # =========================================================================
    print("\n" + "="*80)
    print("CATEGORY 9: WITH VALID ATTRIBUTES (10 queries)")
    print("="*80)
    
    attr_queries = [
        "get vms with vm_name",
        "fetch vms with power_state",
        "show vms with cpu_usage_ppm",
        "get vms with memory_mb",
        "fetch clusters with cluster_name",
        "show hosts with host_name",
        "get vms with num_vcpus",
        "fetch vms with hypervisor_type",
        "show clusters with num_nodes",
        "get hosts with cpu_capacity_hz"
    ]
    
    for i, query in enumerate(attr_queries, 1):
        tester.test_query(f"Attr-{i}", query, "Attributes")
    
    # =========================================================================
    # CATEGORY 10: COMPLEX CASUAL QUERIES (5 queries)
    # =========================================================================
    print("\n" + "="*80)
    print("CATEGORY 10: COMPLEX CASUAL QUERIES (5 queries)")
    print("="*80)
    
    complex_queries = [
        "yo get me first 50 vms that are on",
        "show me vms where cpu is high",
        "gimme vms with name and memory",
        "list vms grouped by cluster",
        "count how many vms we got"
    ]
    
    for i, query in enumerate(complex_queries, 1):
        tester.test_query(f"Complex-{i}", query, "Complex")
    
    # Print summary
    tester.print_summary()
    
    return tester.passed, tester.failed


if __name__ == "__main__":
    passed, failed = main()
    exit(0 if failed == 0 else 1)
