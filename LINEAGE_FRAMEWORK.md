# Generic Lineage POC

## Overview

A proof of concept for a **generic, three-axis graph traversal framework** that queries Neo4j-based lineage across derivation, hierarchy, and association relationships — with constrained traversal rules that prevent unbounded graph explosion.

The core insight: graph-based lineage has three fundamentally different "directions" of traversal, and each needs different constraints. Derivation and hierarchy can be followed indefinitely, but associations (cross-cutting relationships) must be limited to prevent the query from returning the entire graph.

This project extends an existing graph project boilerplate that provides Docker-based Neo4j infrastructure, a metamodel-driven graph loader with schema validation, and a FastAPI backend scaffold.

## Project Structure

```
lineage-poc/
├── backend/                     # FastAPI backend service
│   ├── api.py                  # RESTful API endpoints (extend with /lineage/traverse)
│   ├── models.py               # Pydantic request/response models for traversal API
│   ├── requirements.txt        # Python dependencies
│   └── Dockerfile              # Backend container config
│
├── metamodel/
│   ├── schema.yaml             # Metamodel schema — valid node types & relationships
│   └── entities.yaml           # Entity data — nodes and edges loaded into Neo4j
│
├── src/
│   ├── graph/
│   │   └── loader.py           # Neo4j graph loading (reads entities.yaml, validates against schema.yaml)
│   ├── traversal/              # Three-axis traversal engine
│   │   ├── __init__.py
│   │   ├── taxonomy.py         # Loads edge_taxonomy.yaml, classifies edges by axis
│   │   ├── engine.py           # Core BFS traversal with axis constraints
│   │   └── hop_collapsing.py   # Groups X-axis edges into logical lineage steps
│   └── utils.py                # Shared utilities and configuration
│
├── scripts/
│   └── setup_graph.py          # Setup Neo4j graph from metamodel
│
├── tests/
│   ├── conftest.py             # Neo4j test fixtures, seed data loading
│   ├── test_taxonomy.py        # Edge classification unit tests
│   ├── test_traversal.py       # Traversal engine tests (from test_scenarios.yaml)
│   ├── test_hop_collapsing.py  # Hop grouping logic tests
│   └── test_api.py             # API integration tests
│
├── docker-compose.yml          # Complete infrastructure stack (Neo4j + backend)
├── edge_taxonomy.yaml          # Edge axis classification config (query-time only)
├── seed_graph.cypher           # Reference Cypher — canonical seed data definition
├── test_scenarios.yaml         # Validation test cases for all traversal patterns
├── requirements.txt
└── README.md
```

### Two Config Layers

This project separates **graph loading** from **graph querying** with distinct config files:

| File | Used By | Purpose |
|------|---------|---------|
| `metamodel/schema.yaml` | `src/graph/loader.py` | Write-time validation — which node types and relationships are allowed |
| `metamodel/entities.yaml` | `src/graph/loader.py` | The actual nodes and edges to load into Neo4j |
| `edge_taxonomy.yaml` | `src/traversal/taxonomy.py` | Read-time classification — how to traverse edges (axis, direction, hop groups) |

The schema says "these relationships are valid." The taxonomy says "this is how to traverse them." Same edges, different perspectives.

## Getting Started

```bash
# Start Neo4j
docker-compose up -d

# Load the graph
python scripts/setup_graph.py

# Start the API
cd backend && uvicorn api:app --reload
```

## The Three-Axis Model

### X-Axis: Lineage (Derivation)

Horizontal. Represents data flow and transformation — how one resource is derived from another.

**Key pattern:** Resources don't connect directly. They flow through **transformer nodes** (ETL jobs, data dependencies). A single "lineage hop" is actually two graph edges:

```
Resource --[consumed_by]--> Transformer --[produced_by]--> Resource
```

Examples:
- `Dataset → ETL Job → Dataset` (dataset-level lineage)
- `Attribute → Data Dependency → Attribute` (column-level lineage)
- `Dataset → Training Job → Model Version` (cross-type derivation)

**Constraint:** Unlimited depth. Follow the full derivation chain.

**Hop Collapsing:** Two physical edges (resource→transformer→resource) are presented as one logical lineage step. The transformer node is included as metadata, not as a separate step in the path.

### Y-Axis: Hierarchy (Parent-Child)

Vertical. Represents containment, versioning, and structural relationships.

Examples:
- `Agentic System → Agentic System Version → Agent Version`
- `Dataset → Attributes`
- `Glossary → Sub-Glossary → Business Terms`
- `Model → Model Versions`

**Constraint:** Unlimited depth. Walk the full tree.

**Semantic Direction:** The production graph stores edges in whatever direction they were originally modeled (not always consistent). Rather than flipping edges in production, the taxonomy config defines a `semantic_up` property that tells the query engine which direction to traverse for "up" vs "down" regardless of stored edge direction. **Read and translate, don't mutate.**

### Z-Axis: Association (Cross-Cutting)

Lateral. Represents relationships that are neither derivation nor containment — but are still meaningful. These connect resources across domains.

Examples:
- `Agent Version --[uses]--> Dataset`
- `Workspace --[workspace_dataset]--> Dataset`
- `Use Case --[use_case_dataset]--> Dataset`
- `Result Set --[resultsets_report]--> Report` (data quality linkage)

**Constraint: Maximum 1 hop.** After reaching an associated node via Z-axis, traversal may continue on X or Y axes only. **Z-of-Z is explicitly blocked.**

This is the critical constraint. Without it, associations-of-associations would fan out across the entire graph. The Z-axis answers "what else is related to this node?" — but not "what's related to the related things?"

### Traversal Rules Summary

| Axis | Max Depth | After Z-Hop? | Direction Modes |
|------|-----------|--------------|-----------------|
| X (Lineage) | Unlimited | Allowed | upstream, downstream, both |
| Y (Hierarchy) | Unlimited | Allowed | up, down, both |
| Z (Association) | **1 hop** | **Blocked** (no Z-of-Z) | undirected |

### Allowed vs Blocked Traversal Examples

```
✅ X → X → X                     (follow full derivation chain)
✅ Y → Y → Y                     (walk full hierarchy)
✅ X → Z → Y                     (find association, then walk its hierarchy)
✅ Z → X → X                     (from association, follow its lineage)
✅ Z → Y → Y                     (from association, walk its hierarchy)
❌ Z → Z                          (association of association — BLOCKED)
❌ X → Z → Z                     (lineage then two associations — BLOCKED)
❌ Z → Y → Z                     (hierarchy after Z is fine, but can't Z again)
```

## Additional Design Concepts

### Passthrough Nodes

Some node types exist in the graph for structural reasons but should be **collapsed** in user-facing output. For example, `process_dataset` is a linkage node between `process` and `dataset` — users see processes and datasets, not the join node. The taxonomy config marks these as `visible: false` and the query engine traverses through them but omits or collapses them in results.

### Node Roles

Every node type is classified by its role in `edge_taxonomy.yaml`:
- **resource** — first-class entity the user cares about (dataset, model, report)
- **transformer** — "verb" node that connects resources on X-axis (etl_job, data_dependency)
- **structural** — graph plumbing that may be collapsed (process_dataset)
- **container** — organizational grouping (workspace, glossary)
- **qualifier** — provides context but isn't a primary lineage participant (use_case, resultset)

## Seed Scenario: Fraud Detection Pipeline

The seed data in `metamodel/entities.yaml` (defined canonically in `seed_graph.cypher`) models an end-to-end fraud detection system with ~35 nodes and ~55 edges across all three axes:

```
                                    ┌─────────────────────┐
                                    │  enterprise_glossary │
                                    │    └─ risk_glossary  │
                                    │       └─ terms       │
                                    └────────┬────────────┘
                                             │ Z (is_mapped_to)
                                             ▼
raw_transactions ──X──► curated_transactions ──X──► fraud_feature_set ──X──► fraud_detection_v2.0
     (ds-001)      job    (ds-002)            job    (ds-003)          job    (mv-002)
                          │  │  │                    │                        │
                          │  │  │ Y (attributes)     │ Y (attributes)        │ Y (model→version)
                          │  │  ▼                    ▼                       ▼
                          │  │  account_id           avg_transaction_30d     fraud_detection_model
                          │  │  transaction_amount   txn_frequency_7d
                          │  │  is_fraud
                          │  │
                          │  │ Z (associations)
                          │  ├──► fraud_detection (use_case)
                          │  ├──► fraud_detection_workspace
                          │  └──► txn_quality_results (resultset)
                          │
                          ▼ X (scoring)
                   fraud_predictions ◄──Z── fraud_reviewer_agent_v1
                     (ds-004)                      │ Z (uses)
                                                   ├──► mcp_tool
                                                   └──► model_version_v2
```

## API

### POST /lineage/traverse

```json
{
  "start_node_id": "ds-002",
  "axes": ["x", "y", "z"],
  "x_direction": "both",
  "y_direction": "both",
  "max_z_hops": 1,
  "max_depth": null,
  "include_transformers": true
}
```

See `CLAUDE_CODE_PROMPT.md` for full response schema and implementation details.

## Testing

Test scenarios are defined in `test_scenarios.yaml` — 13 cases covering all axis combinations. The critical test is `XZ-02`: validates that Z-of-Z is blocked while Z→X and Z→Y continuations are allowed.

```bash
pytest tests/ -v
```

## Implementation Details

See `CLAUDE_CODE_PROMPT.md` for the full implementation specification including traversal algorithm, edge classification logic, hop collapsing, and semantic direction handling.