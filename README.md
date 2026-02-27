# Graph Analytics with Neo4j

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

### Connect to Neo4j:

Option 1 - Spin up locally Neo4j instance:

```bash
docker-compose up -d
```
This will start:
- **Neo4j** at `http://localhost:7474` (Browser UI) and `bolt://localhost:7687` (Database)
  - Username: `neo4j`
  - Password: `password`

Option 2 - Connect to sandbox instance in JPMC

Create a .env file in the project root with these 3 variables
```bash
# .env file
NEO4J_URI=bolt://wh-18c5a7721d.svr.us.jpmchase:7687/
NEO4J_USER=your_sid
NEO4J_PASSWORD=password #the one you set for the sandbox
```

### Run FastAPI Traversal Engine

```bash
pip install -r requirements.txt

cd backend
uvicorn api:app --reload 
```
This will start: 
- **Backend API** at `http://localhost:8000` (API docs at `/docs`)


## Usage

### 1. Load Data into Neo4j

Note: If using in JPMC data may already be loaded.

```bash
# Load the graph
python scripts/setup_graph.py --schema-version v2 --entities-version large-1000
```

This will:
- Load entities from `metamodel/entities.yaml`
- Create nodes and relationships in Neo4j
- Generate Node2Vec embeddings using Graph Data Science (GDS)

### 2. Explore with the Visual Interface

Open your browser and navigate to:
- **API Documentation**: `http://localhost:8000/docs`
- **Neo4j Browser**: `http://localhost:7474` or http://wh-18c5a7721d.svr.us.jpmchase:7474/ (JPMC)


### Use Cases

Explore common lineage queries using the multi-axis traversal engine.

---

#### 1. 🤖 **Agentic System Lineage**
> *What are the complete upstream data sources for this agentic system?*

<details>
<summary><b>📋 View Parameters</b></summary>

| Parameter | Value |
|-----------|-------|
| **Base Node** | `fraud-asysv-001` |
| **Lineage (X-axis)** | ✅ On, Upstream |
| **Hierarchy (Y-axis)** | ✅ On |
| **Association (Z-axis)** | ✅ On, Outgoing |
| **Governance (G-axis)** | ❌ Off |

</details>

![Agentic System Lineage Snapshot](images/questions-answered/agent-systems.png)

---

#### 2. 🏗️ **Model Infrastructure Lineage**
> *Where was this model developed and using what components?*

<details>
<summary><b>📋 View Parameters</b></summary>

| Parameter | Value |
|-----------|-------|
| **Base Node** | `fraud-mv-001` |
| **Lineage (X-axis)** | ✅ On, Upstream |
| **Hierarchy (Y-axis)** | ✅ On |
| **Association (Z-axis)** | ✅ On, Outgoing |
| **Governance (G-axis)** | ❌ Off |

</details>

![Infra Lineage Snapshot](images/questions-answered/infra-lineage.png)

---

#### 3. 💥 **Model Deprecation Impact Analysis**
> *If this Model Version was deprecated, what Use Cases are impacted?*

<details>
<summary><b>📋 View Parameters</b></summary>

| Parameter | Value |
|-----------|-------|
| **Base Node** | `fraud-mv-002` |
| **Lineage (X-axis)** | ❌ Off |
| **Hierarchy (Y-axis)** | ✅ On (6+ hops) |
| **Association (Z-axis)** | ✅ On, Incoming |
| **Governance (G-axis)** | ❌ Off |

</details>

![Model Version Blast Radius](images/questions-answered/model-deprecation.png)

---

#### 4. 📚 **Glossary Term Impact Analysis**
> *If this Business Element Term is edited, what Attributes are impacted?*

<details>
<summary><b>📋 View Parameters</b></summary>

| Parameter | Value |
|-----------|-------|
| **Base Node** | `term-002` |
| **Lineage (X-axis)** | ❌ Off |
| **Hierarchy (Y-axis)** | ✅ On |
| **Association (Z-axis)** | ✅ On |
| **Governance (G-axis)** | ❌ Off |

</details>

![Term Blast Radius](images/questions-answered/glossary-edit.png)

---

#### 5. 📊 **Downstream, Data-Only Lineage**
> *How many downstream consumer systems do I have, how critical are they?*

<details>
<summary><b>📋 View Parameters</b></summary>

| Parameter | Value |
|-----------|-------|
| **Base Node** | `fraud-ds-002` |
| **Lineage (X-axis)** | ✅ On, Downstream |
| **Hierarchy (Y-axis)** | ❌ Off |
| **Association (Z-axis)** | ❌ Off |
| **Governance (G-axis)** | ❌ Off |

</details>

![Downstream Resources](images/questions-answered/downstream.png)

---

#### 6. ✅ **Data Quality Monitoring**
> *Is the data I'm receiving complete & accurate?*

<details>
<summary><b>📋 View Parameters</b></summary>

| Parameter | Value |
|-----------|-------|
| **Base Node** | `risk-app-001` |
| **Lineage (X-axis)** | ✅ On |
| **Hierarchy (Y-axis)** | ❌ Off |
| **Association (Z-axis)** | ❌ Off |
| **Governance (G-axis)** | ✅ On |

</details>

![TDQ](images/questions-answered/tdq.png)

#### 7. 🎯 **Use Case Exploration**
> *All the things in my Use Case*

<details>
<summary><b>📋 View Parameters</b></summary>

| Parameter | Value |
|-----------|-------|
| **Base Node** | `uc-001` |
| **Lineage (X-axis)** | ❌ Off |
| **Hierarchy (Y-axis)** | ✅ On |
| **Association (Z-axis)** | ✅ On, Both |
| **Governance (G-axis)** | ❌ Off |

</details>

![Use Case](images/questions-answered/use-case.png)

---


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

