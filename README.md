# Graph Analytics with Neo4j & Lineage Explorer

A modular graph analytics system for building and querying knowledge graphs with Neo4j, featuring:
- **Interactive Graph Visualization** - Modern web-based lineage explorer UI
- **Node-Specific Lineage Viewer** - EQTY Lab Lineage Explorer integration
- **RESTful API** - FastAPI backend for graph queries and analysis
- **Hybrid Search** - BM25, semantic embeddings, and graph-based retrieval
- **Docker-based Deployment** - Complete stack with Neo4j, backend API, and frontend

## Project Structure

```
graph-analytics/
├── frontend/                    # Graph visualization frontend
│   ├── index.html              # Interactive lineage explorer UI
│   └── lineage-explorer-original/  # Original HuggingFace repo
│
├── backend/                     # FastAPI backend service
│   ├── api.py                  # RESTful API endpoints
│   ├── requirements.txt        # Python dependencies
│   └── Dockerfile              # Backend container config
│
├── metamodel/
│   ├── schema.yaml             # Metamodel schema definition
│   └── entities.yaml           # Entity data (use cases, models, datasets, attributes)
│
├── src/
│   ├── graph/
│   │   ├── loader.py           # Neo4j graph loading
│   │   └── embeddings.py       # Graph embedding management
│   └── utils.py                # Shared utilities and configuration
│
├── scripts/
│   ├── setup_graph.py          # Setup Neo4j graph from metamodel
│   └── search.py               # Perform hybrid searches
│
├── docker-compose.yml          # Complete infrastructure stack
├── requirements.txt
└── README.md
```

## Prerequisites

- Docker and Docker Compose
- Python 3.8+
- pip

## Quick Start

### Option 1: Full Stack with Docker (Recommended)

Start all services (Neo4j, Backend API, and Frontend) with a single command:

```bash
docker-compose up -d
```

This will start:
- **Neo4j** at `http://localhost:7474` (Browser UI) and `bolt://localhost:7687` (Database)
  - Username: `neo4j`
  - Password: `password`
- **Backend API** at `http://localhost:8000` (API docs at `/docs`)
- **Node Selector Frontend** at `http://localhost:3000`
- **Lineage Explorer** at `http://localhost:7860`

### Option 2: Development Setup

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -r backend/requirements.txt
   ```

2. **Start Neo4j only:**
   ```bash
   docker-compose up neo4j -d
   ```

3. **Run backend API locally:**
   ```bash
   cd backend
   python api.py
   # API will be available at http://localhost:8000
   ```

4. **Serve frontend locally:**
   ```bash
   # Using Python's built-in HTTP server
   cd frontend
   python -m http.server 3000
   # Frontend will be available at http://localhost:3000
   ```

## Usage

### 1. Load Data into Neo4j

Load your metamodel data into Neo4j:

```bash
# Install dependencies first
pip install -r requirements.txt

# Load the graph
python scripts/setup_graph.py
```

This will:
- Load entities from `metamodel/entities.yaml`
- Create nodes and relationships in Neo4j
- Generate Node2Vec embeddings using Graph Data Science (GDS)

### 2. Explore with the Visual Interface

Open your browser and navigate to:
- **Frontend Visualization**: `http://localhost:3000`
- **API Documentation**: `http://localhost:8000/docs`
- **Neo4j Browser**: `http://localhost:7474`

### 3. Using the Lineage Explorer

The frontend provides an interactive graph visualization with:

**Features:**
- 🔍 **Search**: Search for nodes by name, title, or description
- 🎯 **Click**: Click on nodes to view detailed properties
- 🔗 **Double-click**: Double-click nodes to load their neighbors
- 📊 **Statistics**: View graph statistics in the sidebar
- 🎨 **Color-coded**: Different node types have different colors
- 🔄 **Interactive**: Drag nodes, zoom, and pan around the graph

**Keyboard Shortcuts:**
- Arrow keys: Navigate the graph
- Mouse wheel: Zoom in/out
- Click + drag: Pan the view

### 4. Using the API

The backend provides RESTful endpoints for programmatic access:

```bash
# Get entire graph
curl http://localhost:8000/api/graph

# Get specific node with neighbors
curl http://localhost:8000/api/graph/node/use_case_001

# Search nodes
curl http://localhost:8000/api/graph/search?q=customer

# Get lineage (upstream/downstream/both)
curl http://localhost:8000/api/graph/lineage/dataset_001?direction=both

# Get graph statistics
curl http://localhost:8000/api/graph/stats
```

API documentation is available at `http://localhost:8000/docs` (Swagger UI) or `http://localhost:8000/redoc` (ReDoc).

### 5. View Node Lineage (New!)

Select a specific node and visualize its complete lineage:

**Using the Node Selector UI:**

1. Open `http://localhost:3000`
2. Browse or search for a node (e.g., "Feature Store v2" or "ds-009")
3. Click the "View Lineage →" button
4. The lineage data will be downloaded as a JSON file
5. Open `http://localhost:7860` (Lineage Explorer)
6. Paste the JSON to visualize the lineage

**Using the API:**

```bash
# Get lineage data for a specific node in EQTY Lab format
curl "http://localhost:8000/api/lineage-explorer/ds-009?direction=both" > lineage.json

# View lineage for a model
curl "http://localhost:8000/api/lineage-explorer/mdl-001?direction=upstream"

# View lineage for a use case
curl "http://localhost:8000/api/lineage-explorer/uc-001?direction=downstream"
```

**Lineage Directions:**
- `upstream`: Shows what the node depends on (ancestors)
- `downstream`: Shows what depends on the node (descendants)
- `both`: Shows complete lineage graph (default)

📖 **For detailed instructions, see [LINEAGE_EXPLORER_GUIDE.md](LINEAGE_EXPLORER_GUIDE.md)**

### 6. Perform Searches (Optional)

Run hybrid searches using the CLI:

```bash
# Default query
python scripts/search.py

# Custom query
python scripts/search.py "your search query here"

# Limit number of results
python scripts/search.py "your query" --top-n 5
```

## Configuration

Environment variables (optional):

```bash
# Neo4j
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="password"
```


## API Endpoints

The backend API provides the following endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check and Neo4j connection status |
| `/api/graph` | GET | Get entire graph (nodes and edges) |
| `/api/graph/nodes` | GET | Get all nodes, optionally filtered by label |
| `/api/graph/edges` | GET | Get all edges, optionally filtered by type |
| `/api/graph/node/{node_id}` | GET | Get node with neighbors (depth configurable) |
| `/api/graph/search?q={query}` | GET | Search nodes by property values |
| `/api/graph/stats` | GET | Get graph statistics |
| `/api/graph/lineage/{node_id}` | GET | Get lineage (upstream/downstream/both) |

## Customization

### Adding Custom Node Types

1. Update `metamodel/schema.yaml` with new node types and their properties
2. Add entity data to `metamodel/entities.yaml`
3. Reload the graph: `python scripts/setup_graph.py`
4. Update the color palette in `frontend/index.html` (optional):

```javascript
const colorPalette = {
    'YourNodeType': '#your-color-hex',
    // ... other types
};
```

### Modifying the Visualization

The frontend uses vis.js for graph visualization. You can customize:
- **Layout**: Change the physics engine settings in `frontend/index.html`
- **Styling**: Update CSS variables and node colors
- **Interactions**: Add new event listeners for custom behaviors

### Extending the API

Add new endpoints in `backend/api.py`:

```python
@app.get("/api/your-endpoint")
async def your_endpoint():
    # Your logic here
    return {"data": "your data"}
```

## Troubleshooting

**Frontend can't connect to API:**
- Ensure backend is running: `curl http://localhost:8000/api/health`
- Check CORS settings in `backend/api.py`
- Verify API_BASE URL in `frontend/index.html`

**No data in visualization:**
- Ensure graph is loaded: `python scripts/setup_graph.py`
- Check Neo4j has data: Visit `http://localhost:7474` and run `MATCH (n) RETURN n LIMIT 10`
- Check API response: `curl http://localhost:8000/api/graph`

**Docker services won't start:**
- Check ports aren't in use: `lsof -i :7474,7687,8000,3000`
- View logs: `docker-compose logs -f [service-name]`
- Rebuild containers: `docker-compose up --build`

### Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes all data)
docker-compose down -v

## License

[Your License Here]

## Contributing

[Your Contributing Guidelines Here]
