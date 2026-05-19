# IDF Query UI

**Natural Language Interface for IDF Queries**

A web-based interface for translating natural language queries into IDF RPC calls with real-time validation, multi-language code generation, and feedback learning.

---

## Features

✅ **Natural Language Input** - Type queries in plain English  
✅ **Real-time Translation** - Instant query generation  
✅ **Multi-Language Output** - Python, C++, Java, Golang code  
✅ **Feedback System** - Improve accuracy through corrections  
✅ **Semantic Understanding** - Hybrid keyword + embedding model  
✅ **Attribute Validation** - Only valid attributes suggested  

---

## Quick Start

### 1. Start All Services
```bash
./start.sh
```

This starts:
- MCP Server (port 8000)
- Backend API (port 3001)
- Frontend UI (port 3000)

### 2. Open Browser
```
http://localhost:3000
```

### 3. Stop Services
```bash
./stop.sh
```

---

## Usage

### Enter Natural Language Query
Type any query in plain English:
- "Get all VMs"
- "Show me VMs where cpu is high"
- "Fetch first 100 powered on VMs with vm_name"
- "Group VMs by cluster with sum of memory"

### View Generated Output
Switch between tabs to see:
- **Protobuf JSON** - IDF query structure
- **Python Code** - Python client code
- **C++ Code** - C++ client code
- **Java Code** - Java client code
- **Go Code** - Golang client code

### Submit Feedback
If the output is incorrect:
1. Click "Provide Feedback"
2. Paste the corrected output
3. Click "Submit Feedback"

The system learns from your corrections!

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (HTML/JS)                        │
│                   http://localhost:3000                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                 Backend API (FastAPI)                        │
│                   http://localhost:3001                      │
│  • Keyword-based detection (fast)                            │
│  • Embedding model fallback (accurate)                       │
│  • MCP server integration                                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  MCP Server (FastAPI)                        │
│                   http://localhost:8000                      │
│  • Query translation                                         │
│  • Attribute validation                                      │
│  • Code generation                                           │
│  • Learning system                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Backend API

### Endpoints

#### `POST /generate`
Generate IDF query from natural language.

**Request:**
```json
{
  "query": "Get all VMs with vm_name"
}
```

**Response:**
```json
{
  "success": true,
  "entity_type": "vm",
  "rpc": "GetEntitiesWithMetrics",
  "confidence": 0.95,
  "protobuf_json": { /* query structure */ },
  "python_code": "# Python code...",
  "cpp_code": "// C++ code...",
  "java_code": "// Java code...",
  "golang_code": "// Go code..."
}
```

#### `POST /feedback`
Submit feedback for learning.

**Request:**
```json
{
  "query": "Get all VMs",
  "generated_output": "{ /* generated */ }",
  "corrected_output": "{ /* corrected */ }"
}
```

---

## Configuration

### Backend (`backend/app.py`)

**Embedding Model:**
```python
EMBEDDING_API_URL = "https://hkn12.ai.nutanix.com/enterpriseai/v1/embeddings"
API_KEY = "f8228bd2-b97e-4325-aeb1-9b6bd2d70a19"
MODEL_NAME = "hack-embed"
```

**MCP Server:**
```python
MCP_SERVER_URL = "http://localhost:8000"
```

### Frontend (`frontend/index.html`)

**Backend API:**
```javascript
const API_URL = 'http://localhost:3001/generate';
```

---

## Testing

### Comprehensive Test Suite
Tests 37 query patterns including:
- Basic entity queries
- Limit queries
- Where clauses
- Raw columns
- Group by
- Aggregation
- Count queries
- Cursor queries
- Combined queries

```bash
python3 comprehensive_query_tests.py
```

### Extensive Language Tests
Tests 120+ queries with diverse patterns:
- Casual English
- Broken English
- Questions
- Typos
- Mixed case
- Complex combinations

```bash
python3 extensive_language_tests.py
```

---

## Example Queries

### Basic
- "Get all VMs"
- "Fetch clusters"
- "Show hosts"

### With Attributes
- "Get VMs with vm_name and memory_mb"
- "Fetch clusters with cluster_name"

### Filtering
- "Get VMs where cpu_usage_ppm > 500000"
- "Find VMs that are powered on"
- "Show VMs where memory is high"

### Pagination
- "Get first 100 VMs"
- "Fetch VMs using cursor query"
- "Get top 50 clusters"

### Grouping
- "Group VMs by cluster_name"
- "Group hosts by hypervisor_type"

### Aggregation
- "Get sum of memory_mb for all VMs"
- "Calculate average cpu_usage_ppm"
- "Count all VMs"

### Complex
- "Get first 100 powered on VMs with vm_name where cpu_usage_ppm > 500000"
- "Group VMs by cluster with sum of memory using cursor query"

### Casual/Broken English
- "gimme all vms"
- "show me vms where cpu is high"
- "vm where cpu high"
- "yo get me first 50 vms that are on"

---

## Files

### Backend
- `backend/app.py` - FastAPI backend server
- `backend/requirements.txt` - Python dependencies

### Frontend
- `frontend/index.html` - Main UI
- `frontend/try-me.html` - Try-me editor
- `frontend/examples.html` - Example queries

### Tests
- `comprehensive_query_tests.py` - 37 query tests
- `extensive_language_tests.py` - 120+ language pattern tests
- `test_ui_comprehensive.py` - UI integration tests

### Scripts
- `start.sh` - Start all services
- `stop.sh` - Stop all services

---

## Performance

### Query Generation
- **Keyword-based:** ~50ms
- **Embedding-based:** ~200ms
- **Hybrid approach:** Optimal balance

### Response Times
- Simple queries: 50-100ms
- Complex queries: 100-200ms
- With validation: +10-20ms

---

## Troubleshooting

### Services won't start
```bash
# Check if ports are in use
lsof -i :8000  # MCP Server
lsof -i :3001  # Backend
lsof -i :3000  # Frontend

# Kill processes
./stop.sh
```

### Backend errors
```bash
# Check backend logs
tail -f /tmp/backend.log

# Restart backend
lsof -ti:3001 | xargs kill -9
cd backend && python3 app.py &
```

### MCP server not responding
```bash
# Check MCP logs
tail -f /tmp/mcp.log

# Restart MCP server
lsof -ti:8000 | xargs kill -9
cd ../idf_mcp_server && python3 server.py &
```

### Frontend not loading
```bash
# Restart frontend
lsof -ti:3000 | xargs kill -9
cd frontend && python3 -m http.server 3000 &
```

---

## Development

### Adding New Query Patterns

1. Update `query_translator.py` in MCP server
2. Add test cases to `comprehensive_query_tests.py`
3. Test with `python3 comprehensive_query_tests.py`
4. Submit feedback through UI for learning

### Modifying UI

Edit `frontend/index.html` and refresh browser.

### Updating Backend Logic

Edit `backend/app.py` and restart:
```bash
lsof -ti:3001 | xargs kill -9
cd backend && python3 app.py &
```

---

## Dependencies

### Backend
```
fastapi
uvicorn
requests
numpy
```

### Frontend
- Bootstrap 4.5
- jQuery 3.5
- Font Awesome 5.15

---

## License

Internal Nutanix tool.

---

## Support

For issues or questions, contact the IDF team.
