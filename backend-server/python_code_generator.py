"""
Python IDF query code generator.

Generates executable Python code that matches the exact pattern from
the Try Me Editor. Supports ALL IDF APIs by auto-detecting the API method
from the proto structure or an explicit api_method parameter.

Supported APIs:
- GetEntitiesWithMetrics (default for query { } protos)
- UpdateEntity (entity_guid + attribute_data_arg_list)
- DeleteEntity (entity_guid without attributes)
- RegisterMetricTypes (metric_type_list)
- RegisterEntityTypes (entity_type_list)
- BatchGetEntitiesWithMetrics (query_list)
- GetEntities (entity_guid_list)
- Watch: register, unregister, get (sub-type auto-detected from NL query)
"""

import re
from typing import Optional


API_TEMPLATES = {
    "GetEntitiesWithMetrics": {
        "arg_type": "GetEntitiesWithMetricsArg",
        "method": "GetEntitiesWithMetrics",
    },
    "UpdateEntity": {
        "arg_type": "UpdateEntityArg",
        "method": "UpdateEntity",
    },
    "DeleteEntity": {
        "arg_type": "DeleteEntityArg",
        "method": "DeleteEntity",
    },
    "RegisterMetricTypes": {
        "arg_type": "RegisterMetricTypesArg",
        "method": "RegisterMetricTypes",
    },
    "UnregisterMetricTypes": {
        "arg_type": "UnregisterMetricTypesArg",
        "method": "UnregisterMetricTypes",
    },
    "RegisterEntityTypes": {
        "arg_type": "RegisterEntityTypesArg",
        "method": "RegisterEntityTypes",
    },
    "BatchGetEntitiesWithMetrics": {
        "arg_type": "BatchGetEntitiesWithMetricsArg",
        "method": "BatchGetEntitiesWithMetrics",
    },
    "BatchUpdateEntities": {
        "arg_type": "BatchUpdateEntitiesArg",
        "method": "BatchUpdateEntities",
    },
    "BatchDeleteEntities": {
        "arg_type": "BatchDeleteEntitiesArg",
        "method": "BatchDeleteEntities",
    },
    "GetEntities": {
        "arg_type": "GetEntitiesArg",
        "method": "GetEntities",
    },
    "GetEntityTypes": {
        "arg_type": "GetEntityTypesArg",
        "method": "GetEntityTypes",
    },
    "GetMetricTypes": {
        "arg_type": "GetMetricTypesArg",
        "method": "GetMetricTypes",
    },
    "GetMetricData": {
        "arg_type": "GetMetricDataArg",
        "method": "GetMetricData",
    },
    "PutMetricData": {
        "arg_type": "PutMetricDataArg",
        "method": "PutMetricData",
    },
    "GetMasterLocation": {
        "arg_type": "GetMasterLocationArg",
        "method": "GetMasterLocation",
    },
    "SpotLightSearch": {
        "arg_type": "SpotLightSearchArg",
        "method": "SpotLightSearch",
    },
    "GetEntitiesTrail": {
        "arg_type": "GetEntitiesTrailArg",
        "method": "GetEntitiesTrail",
    },
    "AttachEntity": {
        "arg_type": "AttachEntityArg",
        "method": "AttachEntity",
    },
    "DetachEntity": {
        "arg_type": "DetachEntityArg",
        "method": "DetachEntity",
    },
    "PutEvent": {
        "arg_type": "PutEventArg",
        "method": "PutEvent",
    },
}


class WatchSubType:
    REGISTER = "register"
    UNREGISTER = "unregister"
    GET = "get"
    WATCH_NEW = "watch_new"
    WATCH_UPDATE = "watch_update"
    WATCH_DELETE = "watch_delete"


def _detect_watch_subtype(natural_language_query: str) -> str:
    """Detect Watch sub-operation from the natural language query."""
    q = natural_language_query.lower().strip()

    if re.search(r'\b(?:delete|remove|unregister|stop|cancel|deregister)\b.*\bwatch\b', q):
        return WatchSubType.UNREGISTER
    if re.search(r'\bwatch\b.*\b(?:delete|remove|unregister|stop|cancel|deregister)\b', q):
        return WatchSubType.UNREGISTER

    if re.search(r'\b(?:get|list|show|check|status|find|retrieve)\b.*\bwatch\b', q):
        return WatchSubType.GET
    if re.search(r'\bwatch\b.*\b(?:status|state|info)\b', q):
        return WatchSubType.GET

    if re.search(r'\bwatch\b.*\b(?:for\s+)?(?:new|creat)', q):
        return WatchSubType.WATCH_NEW
    if re.search(r'\bwatch\b.*\b(?:for\s+)?(?:updat|modif|chang)', q):
        return WatchSubType.WATCH_UPDATE
    if re.search(r'\bwatch\b.*\b(?:for\s+)?(?:delet|remov)', q):
        return WatchSubType.WATCH_DELETE

    return WatchSubType.REGISTER

IDF_PYTHON_TEMPLATE_EMPTY = '''import sys
sys.path.insert(0, "/home/nutanix/cluster/bin")
import env
import gflags
gflags.FLAGS([])
from insights_interface.insights_interface_pb2 import {arg_type}
from insights_interface.insights_interface import InsightsInterface, InsightsInterfaceError

insights_interface = InsightsInterface("{ip}", "{port}")
arg = {arg_type}()
try:
    ret = insights_interface.{method}(arg)
    print(ret)
except InsightsInterfaceError as ex:
    print("Error Message: " + ex.message)
    print(ex.ret)
'''

IDF_PYTHON_TEMPLATE = '''import sys
sys.path.insert(0, "/home/nutanix/cluster/bin")
import env
import gflags
gflags.FLAGS([])
from google.protobuf.text_format import Merge
from insights_interface.insights_interface_pb2 import {arg_type}
from insights_interface.insights_interface import InsightsInterface, InsightsInterfaceError

insights_interface = InsightsInterface("{ip}", "{port}")
arg = {arg_type}()
query = \'\'\'
{proto}
\'\'\'
Merge(query, arg)
try:
    ret = insights_interface.{method}(arg)
    print(ret)
except InsightsInterfaceError as ex:
    print("Error Message: " + ex.message)
    print(ex.ret)
'''


def detect_api_method(proto_text: str) -> str:
    """
    Auto-detect the IDF API method from proto structure.
    Uses key structural markers to identify which API the proto targets.
    """
    stripped = proto_text.strip()

    # Batch operations
    if re.search(r'\bquery_list\s*\{', stripped):
        return "BatchGetEntitiesWithMetrics"
    if re.search(r'\bentity_list\s*\{', stripped) and "attribute_data_arg_list" in stripped:
        return "BatchUpdateEntities"
    if re.search(r'\bentity_list\s*\{', stripped) and "entity_guid" in stripped and "attribute_data" not in stripped:
        return "BatchDeleteEntities"

    # Single entity operations
    if re.search(r'\battribute_data_arg_list\s*\{', stripped):
        return "UpdateEntity"
    if re.search(r'\bentity_guid\s*\{', stripped) and "attribute_data" not in stripped and "entity_guid_list" not in stripped:
        return "DeleteEntity"

    # Schema operations
    if re.search(r'\bmetric_type_list\s*\{', stripped) and "unregister" not in stripped.lower():
        return "RegisterMetricTypes"
    if re.search(r'\bentity_type_info_list\s*\{', stripped):
        return "RegisterEntityTypes"

    # GetEntities (by GUID list)
    if re.search(r'\bentity_guid_list\s*\{', stripped):
        return "GetEntities"

    # GetEntityTypes
    if re.search(r'\bentity_type_name\s*:', stripped) and len(stripped.split('\n')) <= 3 and "query" not in stripped:
        return "GetEntityTypes"

    # Watch operations
    if re.search(r'\bwatch_id\s*:', stripped) or re.search(r'\bwatch_list\s*\{', stripped):
        return "Watch"
    if re.search(r'\bwatch_type_mask\s*:', stripped):
        return "Watch"

    # Metric data operations
    if re.search(r'\bentity_with_metric_list\s*\{', stripped):
        return "PutMetricData"
    if re.search(r'\bmetric_name_list\s*:', stripped) or (re.search(r'\bstart_time_usecs\s*:', stripped) and "entity_type_name" in stripped):
        return "GetMetricData"

    # SpotLightSearch
    if re.search(r'\bsearch_term\s*:', stripped):
        return "SpotLightSearch"

    # GetEntitiesTrail
    if re.search(r'\bstart_timestamp_usecs\s*:', stripped) and "entity_guid_list" in stripped:
        return "GetEntitiesTrail"

    # AttachEntity / DetachEntity
    if re.search(r'\bupdate_entity_arg\s*\{', stripped) and "incarnation_id" in stripped:
        return "AttachEntity"
    if re.search(r'\bdelete_entity_arg\s*\{', stripped) and "moved_to_cluster_uuid" in stripped:
        return "DetachEntity"

    # GetMasterLocation (typically empty or minimal)
    if stripped == "" or re.search(r'^\s*$', stripped):
        return "GetMasterLocation"

    # PutEvent
    if re.search(r'\bevent\s*\{', stripped) or re.search(r'\bevent_type\s*:', stripped):
        return "PutEvent"

    # UnregisterMetricTypes
    if "metric_type_list" in stripped and ("unregister" in stripped.lower() or "remove" in stripped.lower()):
        return "UnregisterMetricTypes"

    # GetMetricTypes (regex-based)
    if re.search(r'\bregex\s*:', stripped) and len(stripped.split('\n')) <= 3:
        return "GetMetricTypes"

    return "GetEntitiesWithMetrics"


def generate_python_code(query_proto: str, natural_language_query: str = "",
                         idf_ip: str = "127.0.0.1", idf_port: str = "2027",
                         api_method: Optional[str] = None) -> str:
    """
    Generate Python IDF query code from proto text format.

    Auto-detects the API method from proto structure if api_method is not provided.
    Uses the exact same pattern as the Try Me Editor for all supported APIs.
    
    Args:
        query_proto: Query proto in protobuf text format
        natural_language_query: Original natural language query (for comment)
        idf_ip: IDF instance IP
        idf_port: IDF instance port
        api_method: Explicit API method name (auto-detected if None)
    
    Returns:
        Complete executable Python code string
    """
    if not api_method:
        api_method = detect_api_method(query_proto)

    if api_method == "Watch":
        return _generate_watch_code(query_proto, natural_language_query, idf_ip, idf_port)

    api_info = API_TEMPLATES.get(api_method)
    if not api_info:
        api_info = API_TEMPLATES["GetEntitiesWithMetrics"]

    if api_method == "GetEntitiesWithMetrics":
        proto_text = _ensure_query_wrapper(query_proto)
    else:
        proto_text = query_proto.strip()

    if not proto_text:
        code = IDF_PYTHON_TEMPLATE_EMPTY.format(
            ip=idf_ip,
            port=idf_port,
            arg_type=api_info["arg_type"],
            method=api_info["method"],
        )
    else:
        code = IDF_PYTHON_TEMPLATE.format(
            ip=idf_ip,
            port=idf_port,
            proto=proto_text,
            arg_type=api_info["arg_type"],
            method=api_info["method"],
        )

    if natural_language_query:
        comment = f"# Query: {natural_language_query}\n"
        code = comment + code

    return code


def _generate_watch_code(proto_text: str, natural_language_query: str,
                         idf_ip: str, idf_port: str) -> str:
    """
    Generate executable code for Watch/Subscribe API.
    
    Differentiates between watch sub-operations:
    - REGISTER: composite_watch_on_entities_of_type (subscribe to changes)
    - UNREGISTER: unregister_composite_watch_on_entities_of_type + stop
    - GET: GetFiredWatchList RPC (list active watches)
    - WATCH_NEW: watch_new_entities_of_type (watch for creates only)
    - WATCH_UPDATE: watch_updated_entities_of_type (watch for updates only)
    - WATCH_DELETE: watch_deleted_entities_of_type (watch for deletes only)
    
    All patterns match the Try Me Editor's style.
    """
    subtype = _detect_watch_subtype(natural_language_query)

    entity_match = re.search(r'entity_type_name\s*:\s*"([^"]+)"', proto_text)
    entity_type = entity_match.group(1) if entity_match else "vm"

    client_id_match = re.search(r'client_id\s*:\s*"([^"]+)"', proto_text)
    client_id = client_id_match.group(1) if client_id_match else f"watch_{entity_type}_client"

    watch_name_match = re.search(r'watch_name\s*:\s*"([^"]+)"', proto_text)
    watch_name = watch_name_match.group(1) if watch_name_match else None
    if not watch_name:
        name_from_nl = re.search(r'(?:named?|name)\s+(?:as\s+)?["\']?(\w+)["\']?', natural_language_query, re.IGNORECASE)
        watch_name = name_from_nl.group(1) if name_from_nl else None

    if subtype == WatchSubType.UNREGISTER:
        return _gen_unregister_watch(natural_language_query, entity_type,
                                     client_id, watch_name, idf_ip, idf_port)
    elif subtype == WatchSubType.GET:
        return _gen_get_watch(natural_language_query, client_id,
                              watch_name, idf_ip, idf_port)
    elif subtype == WatchSubType.WATCH_NEW:
        return _gen_typed_watch(natural_language_query, entity_type,
                                client_id, "watch_new_entities_of_type",
                                idf_ip, idf_port)
    elif subtype == WatchSubType.WATCH_UPDATE:
        return _gen_typed_watch(natural_language_query, entity_type,
                                client_id, "watch_updated_entities_of_type",
                                idf_ip, idf_port)
    elif subtype == WatchSubType.WATCH_DELETE:
        return _gen_typed_watch(natural_language_query, entity_type,
                                client_id, "watch_deleted_entities_of_type",
                                idf_ip, idf_port)
    else:
        mask_match = re.search(r'watch_type_mask\s*:\s*(\d+)', proto_text)
        watch_type_mask = int(mask_match.group(1)) if mask_match else 7
        register_create = "True" if (watch_type_mask & 1) else "False"
        register_update = "True" if (watch_type_mask & 2) else "False"
        register_delete = "True" if (watch_type_mask & 4) else "False"
        return _gen_composite_watch(natural_language_query, entity_type,
                                     client_id, register_create,
                                     register_update, register_delete,
                                     idf_ip, idf_port)


def _gen_composite_watch(nl_query: str, entity_type: str, client_id: str,
                          create: str, update: str, delete: str,
                          idf_ip: str, idf_port: str) -> str:
    return f'''# Query: {nl_query}
import env
import gflags
gflags.FLAGS([])
from google.protobuf.text_format import *
from insights_interface.insights_interface_pb2 import *
from insights_interface.insights_watch_client import *

def error_callback(error_str, error_proto):
  print(error_str)
  print(error_proto)

def callback(entity=None, previous=None, error=None):
  print(entity)
  print(previous)
  print(error)

watch_client = InsightsWatchClient("{client_id}", error_callback,
                                   "{idf_ip}", "{idf_port}")

watch_client.start()

current = watch_client.composite_watch_on_entities_of_type(
    entity_type_name="{entity_type}",
    callback=callback,
    register_create_watch={create},
    register_update_watch={update},
    register_delete_watch={delete},
    get_current_entities=True,
    return_previous_entity=False)
'''


def _gen_unregister_watch(nl_query: str, entity_type: str, client_id: str,
                           watch_name: Optional[str],
                           idf_ip: str, idf_port: str) -> str:
    return f'''# Query: {nl_query}
import env
import gflags
gflags.FLAGS([])
from google.protobuf.text_format import *
from insights_interface.insights_interface_pb2 import *
from insights_interface.insights_watch_client import *

def error_callback(error_str, error_proto):
  print(error_str)
  print(error_proto)

watch_client = InsightsWatchClient("{client_id}", error_callback,
                                   "{idf_ip}", "{idf_port}")

watch_client.start()

watch_client.unregister_composite_watch_on_entities_of_type(
    entity_type_name="{entity_type}",
    register_create_watch=True,
    register_update_watch=True,
    register_delete_watch=True)

watch_client.stop()
print("Watch unregistered and client stopped.")
'''


def _gen_get_watch(nl_query: str, client_id: str,
                    watch_name: Optional[str],
                    idf_ip: str, idf_port: str) -> str:
    name_filter = ""
    if watch_name:
        name_filter = f'\nwatch_name_list: "{watch_name}"'
    return f'''# Query: {nl_query}
import env
import gflags
gflags.FLAGS([])
from google.protobuf.text_format import Merge
from insights_interface.insights_interface_pb2 import *
from insights_interface.insights_interface import InsightsInterface, InsightsInterfaceError

insights = InsightsInterface("{idf_ip}", "{idf_port}")

arg = GetFiredWatchListArg()
query = \'\'\'
watch_client {{
  client_id: "{client_id}"
  session_id: "{client_id}_session"
}}{name_filter}
\'\'\'
Merge(query, arg)
try:
    ret = insights.GetFiredWatchList(arg)
    print(ret)
except InsightsInterfaceError as ex:
    print("Error: " + ex.message)
'''


def _gen_typed_watch(nl_query: str, entity_type: str, client_id: str,
                      method_name: str, idf_ip: str, idf_port: str) -> str:
    """Generate code for single-type watch (create/update/delete only)."""
    return f'''# Query: {nl_query}
import env
import gflags
gflags.FLAGS([])
from google.protobuf.text_format import *
from insights_interface.insights_interface_pb2 import *
from insights_interface.insights_watch_client import *

def error_callback(error_str, error_proto):
  print(error_str)
  print(error_proto)

def callback(entity=None, previous=None, error=None):
  print(entity)
  print(previous)
  print(error)

watch_client = InsightsWatchClient("{client_id}", error_callback,
                                   "{idf_ip}", "{idf_port}")

watch_client.start()

current = watch_client.{method_name}(
    entity_type_name="{entity_type}",
    callback=callback,
    get_current_entities=True,
    return_previous_entity=False)
'''


def _ensure_query_wrapper(proto_text: str) -> str:
    """Ensure the proto has the query {{ }} wrapper that IDF expects."""
    stripped = proto_text.strip()
    if stripped.startswith("query {") or stripped.startswith("query{"):
        return stripped
    lines = stripped.split("\n")
    indented = "\n".join(f"  {line}" for line in lines)
    return f"query {{\n{indented}\n}}"
