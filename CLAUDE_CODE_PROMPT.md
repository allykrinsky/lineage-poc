# Claude Code Implementation Prompt

## Context

Read the full `LINEAGE_FRAMEWORK.md` first — it explains the three-axis lineage model, traversal constraints, and design decisions in detail.

This repo is a POC for a generic graph lineage traversal framework. It is built on top of an existing boilerplate for graph projects that already provides:

- A **Docker Compose stack** with a Neo4j container (`docker-compose.yml`)
- A **metamodel-driven graph loader** that reads `metamodel/entities.yaml` and validates relationships against `metamodel/schema.yaml` before loading into Neo4j (`src/graph/loader.py`)
- A **FastAPI backend** scaffold (`backend/api.py`)
- A **setup script** to initialize the graph (`scripts/setup_graph.py`)

**Do not rebuild or replace the existing graph loading infrastructure.** Instead, extend it.

## Existing Project Structure

```
lineage-poc/
├── backend/                     # FastAPI backend service
│   ├── api.py                  # RESTful API endpoints
│   ├── requirements.txt        # Python dependencies
│   └── Dockerfile              # Backend container config
│
├── metamodel/
│   ├── schema.yaml             # Metamodel schema — defines valid node types and relationships
│   └── entities.yaml           # Entity data — the actual nodes and edges to load
│
├── src/
│   ├── graph/
│   │   ├── loader.py           # Neo4j graph loading (reads entities.yaml, validates against schema.yaml)
│   └── utils.py                # Shared utilities and configuration
│
├── scripts/
│   ├── setup_graph.py          # Setup Neo4j graph from metamodel
│
├── docker-compose.yml          # Complete infrastructure stack (includes Neo4j)
├── requirements.txt
└── README.md
```

## What Already Exists vs What Needs to Be Built

### Already exists (DO NOT rebuild):
- `docker-compose.yml` with Neo4j — just use it
- `src/graph/loader.py` — the graph loading mechanism that reads `entities.yaml` and validates against `schema.yaml`
- `scripts/setup_graph.py` — graph initialization script
- `backend/` scaffold with FastAPI and Dockerfile
- `src/utils.py` — shared config/utilities

### Needs to be created or modified:

1. **`metamodel/schema.yaml`** — Populate with the node types and valid relationships from `edge_taxonomy.yaml`. This is the schema the existing loader validates against. Map the edge taxonomy's node types and edges into whatever format `schema.yaml` expects.

2. **`metamodel/entities.yaml`** — Populate with the seed data. Translate the content from `seed_graph.cypher` into the `entities.yaml` format that the existing loader understands. The Cypher file is a reference for _what_ to load — the actual loading should go through the existing `entities.yaml` → `loader.py` pipeline.

3. **`edge_taxonomy.yaml`** — Already exists in the repo root. This is the traversal config, separate from the metamodel schema. The loader doesn't need to know about axis classifications — that's purely for the query engine.

4. **Traversal engine and API** — The new code. See details below.

## Task: Build the Traversal Engine + Extend the API

### 1. Edge Taxonomy Config Loader

Create a module that loads and parses `edge_taxonomy.yaml` into an in-memory config the traversal engine uses to classify edges at query time.

**Location:** `src/traversal/taxonomy.py` or wherever fits the existing project conventions.

### 2. Traversal Engine

The core logic. Given a start node and traversal parameters, it:

- Connects to the existing Neo4j instance (reuse connection config from `src/utils.py`)
- Classifies each edge encountered using the taxonomy config (lookup by edge name + source/destination types)
- Respects axis constraints:
  - **X-axis:** unlimited depth, follows the Resource → Transformer → Resource pattern
  - **Y-axis:** unlimited depth, uses `semantic_up` / `reverse` config to normalize direction
  - **Z-axis:** **max 1 hop from any path origin** — once a Z-hop is taken, subsequent traversal from that node may only continue on X or Y. Z-of-Z is blocked. This is tracked per-path, not globally.
- Supports direction parameters: `upstream`/`downstream` for X, `up`/`down` for Y, `both` for either
- Supports selecting which axes to traverse: any combination of `[x]`, `[y]`, `[z]`, `[x, y]`, `[x, z]`, `[y, z]`, `[x, y, z]`
- Implements **hop collapsing** for X-axis: the API response groups Resource → Transformer → Resource into a single logical step, with the transformer node as metadata
- Handles **passthrough nodes** (node types with `visible: false`): traverses through them but collapses them in the response

**Location:** `src/traversal/engine.py`

### 3. Extend the FastAPI API

Add a traversal endpoint to the existing `backend/api.py`:

```
POST /lineage/traverse
{
  "start_node_id": "ds-002",
  "axes": ["x", "y", "z"],
  "x_direction": "both",      // upstream | downstream | both
  "y_direction": "both",      // up | down | both
  "max_z_hops": 1,            // configurable, default 1
  "max_depth": null,           // optional global depth limit
  "include_transformers": true  // whether to include transformer nodes in response
}
```

Response should return a structured subgraph:
```json
{
  "start_node": { "id": "ds-002", "type": "dataset", "name": "curated_transactions" },
  "nodes": [...],
  "edges": [...],
  "paths": [
    {
      "axis": "x",
      "direction": "upstream",
      "logical_steps": [
        {
          "from": { "id": "ds-002", "type": "dataset" },
          "to": { "id": "ds-001", "type": "dataset" },
          "via": { "id": "job-001", "type": "etl_job", "name": "ingest_raw_transactions" },
          "edge_names": ["dataset_produced_by", "dataset_consumed_by"]
        }
      ]
    }
  ],
  "traversal_metadata": {
    "z_hops_taken": 3,
    "total_nodes_visited": 15,
    "blocked_z_of_z_paths": 2
  }
}
```

### 4. Tests

Implement the scenarios from `test_scenarios.yaml` using `pytest`. The most critical test is `XZ-02` which validates that Z-of-Z traversal is blocked while Z→Y and Z→X continuations are allowed.

**Location:** `tests/` directory.

## Suggested New File Locations

Extend the existing structure — don't reorganize what's already there:

```
lineage-poc/
├── backend/
│   ├── api.py                  # EXTEND — add /lineage/traverse endpoint
│   ├── models.py               # NEW — Pydantic request/response models
│   ├── requirements.txt        # UPDATE — add any new deps
│   └── Dockerfile
│
├── metamodel/
│   ├── schema.yaml             # UPDATE — populate with node types & valid relationships
│   ├── entities.yaml           # UPDATE — populate with seed data (fraud detection scenario)
│
├── src/
│   ├── graph/
│   │   ├── loader.py           # EXISTING — do not modify
│   ├── traversal/              # NEW — traversal engine package
│   │   ├── __init__.py
│   │   ├── taxonomy.py         # loads edge_taxonomy.yaml, classifies edges
│   │   ├── engine.py           # core BFS traversal with axis constraints
│   │   └── hop_collapsing.py   # groups X-axis edges into logical steps
│   └── utils.py                # EXISTING — reuse Neo4j connection config
│
├── scripts/
│   ├── setup_graph.py          # EXISTING — loads entities.yaml via loader.py
│
├── tests/                      # NEW
│   ├── conftest.py             # Neo4j test fixtures
│   ├── test_taxonomy.py        # edge classification unit tests
│   ├── test_traversal.py       # traversal engine tests (from test_scenarios.yaml)
│   ├── test_hop_collapsing.py  # hop grouping logic tests
│   └── test_api.py             # API integration tests
│
├── docker-compose.yml          # EXISTING — already has Neo4j
├── edge_taxonomy.yaml          # Traversal axis config (NOT used by loader — only by query engine)
├── seed_graph.cypher           # Reference only — actual loading goes through entities.yaml
├── test_scenarios.yaml         # Test case definitions
├── requirements.txt            # UPDATE if needed
└── README.md
```

## Architecture Guidance

### Traversal Algorithm

Use BFS (breadth-first search) with per-path state tracking. Each entry in the queue should carry:

```python
@dataclass
class TraversalState:
    node_id: str
    node_type: str
    path: list              # nodes visited to reach here
    z_hops_taken: int       # number of Z-axis hops in this path (max 1)
    last_axis: str          # which axis was used to reach this node (x, y, z)
    depth: int              # total traversal depth
```

When expanding a node:
1. Get all edges from the node
2. For each edge, look up its axis classification from the taxonomy config
3. If the edge is Z-axis and `z_hops_taken >= max_z_hops` → skip (this is the key constraint)
4. If the edge is X-axis, check direction (upstream/downstream) matches request
5. If the edge is Y-axis, use `semantic_up`/`reverse` config to determine if it matches requested direction
6. Add valid neighbors to the queue with updated state

### Edge Classification

The taxonomy config has edges that can share the same name but differ by source/destination type (e.g., `is_consumed_by` appears on both `dataset→etl_job` and `model_version→etl_job`). The classifier must match on `(edge_name, source_type, destination_type)` — not just edge name.

Some edges also have `sub_type` qualifiers (e.g., `attribute` with `sub_type: logical` vs `sub_type: term`). If the config specifies a sub_type, the classifier should check it. If the config doesn't specify a sub_type, it matches any sub_type.

### Hop Collapsing

For X-axis results, group pairs of edges that form a complete lineage hop:

```
Resource A --[edge1]--> Transformer --[edge2]--> Resource B
```

Both `edge1` and `edge2` must belong to the same `hop_group` in the config. Present this as:

```json
{
  "from": "Resource A",
  "to": "Resource B",
  "via": "Transformer",
  "hop_group": "dataset_etl"
}
```

### Semantic Direction Handling

For Y-axis edges, the config has `semantic_up: forward` or `semantic_up: reverse`. This means:
- `semantic_up: forward` → following the stored edge direction goes UP the hierarchy
- `semantic_up: reverse` → following the stored edge direction goes DOWN; to go UP, traverse in reverse

The query engine should normalize this so the caller just says `up` or `down` and the engine figures out the Cypher direction.

## Relationship Between Config Files

There are two separate config concerns — keep them distinct:

| File | Used By | Purpose |
|------|---------|---------|
| `metamodel/schema.yaml` | `src/graph/loader.py` | Validates which node types and relationships are allowed when loading the graph |
| `metamodel/entities.yaml` | `src/graph/loader.py` | The actual node and edge data to load into Neo4j |
| `edge_taxonomy.yaml` | `src/traversal/taxonomy.py` | Classifies edges by axis (X/Y/Z) with semantic direction — used only at query time |

The **schema** says "these relationships are valid." The **taxonomy** says "this is how to traverse them." They describe the same edges but from different perspectives. The schema is for write-time validation; the taxonomy is for read-time query logic.

## Key Constraint to Validate

The single most important thing this POC must prove:

> **After a Z-axis hop, the traversal engine correctly blocks further Z-axis hops while allowing X and Y continuation.**

Test `XZ-02` in `test_scenarios.yaml` spells this out with concrete paths. Make sure this test is implemented and passing before moving to anything else.

## What NOT to Build

- No frontend / visualization (stretch goal, not part of this phase)
- No authentication / authorization
- No production-grade error handling — this is a POC
- No caching layer
- **Don't rebuild the graph loading pipeline** — use the existing `entities.yaml` → `schema.yaml` → `loader.py` mechanism
- Don't over-engineer the API — one traversal endpoint is enough to prove the concept