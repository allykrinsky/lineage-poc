# Graph Analytics with Neo4j & Lineage Explorer

A modular graph analytics system for building and querying knowledge graphs with Neo4j

## Project Structure

```
lineage-poc/
├── backend/                     # FastAPI backend service
│   ├── api.py                  # RESTful API endpoints
│   ├── requirements.txt        # Python dependencies
│   └── Dockerfile              # Backend container config
│
├── metamodel/
│   ├── schema.yaml             # Metamodel schema 
│   └── entities.yaml           # Entity data
|
├── src/
│   ├── graph/
│   │   ├── loader.py           # Neo4j graph loading
│   └── utils.py                # Shared utilities and configuration
│
├── scripts/
│   ├── setup_graph.py          # Setup Neo4j graph from metamodel
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

Start all services (Neo4j, Backend API) with a single command:

```bash
docker-compose up -d
```
This will start:
- **Neo4j** at `http://localhost:7474` (Browser UI) and `bolt://localhost:7687` (Database)
  - Username: `neo4j`
  - Password: `password`
- **Backend API** at `http://localhost:8000` (API docs at `/docs`)


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
- **API Documentation**: `http://localhost:8000/docs`
- **Neo4j Browser**: `http://localhost:7474`


### Example Configurations

Data Only
- base node: fraud-ds-002 
- lineage : On, upstream
- heirarchy : On
- association:  : Off
- governance: Off

Agentic System Exploded
- base node: fraud-asysv-001
- lineage : On, upstream
- heirarchy : On
- association:  : On, outgoing
- governance: Off

All the things in my Use Case 
- base node: uc-001
- lineage : Off
- heirarchy : On
- association:  : On, Both
- governance: Off

TDQ on Data Flows
- base node: risk-app-001
- lineage : Off
- heirarchy : Off
- association:  : Off
- governance: On



## Configuration

Environment variables (optional):

```bash
# Neo4j
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="password"
```

### Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes all data)
docker-compose down -v

