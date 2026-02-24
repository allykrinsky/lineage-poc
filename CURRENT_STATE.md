# Multi-Axis Lineage Traversal: Implementation Guide

## Overview

This document provides a comprehensive technical reference for the multi-axis lineage traversal engine. It describes the architecture, algorithms, constraints, and APIs of the current implementation.


## Traversal Axes

The lineage engine supports four independent traversal axes, each with distinct semantics and constraints.

### X-Axis: Lineage (Derivation)

**Purpose:** Traces data flow and transformations through the graph.

**Edge Pattern:**
Resources connect through transformer nodes (Jobs, DataDependencies):
```
Resource --[IS_CONSUMED_BY]--> Transformer --[PRODUCED_BY]--> Resource
```
**Constraints:**
- **Depth:** Unlimited - follow complete derivation chains
- **Hop Limits:** Optional per-axis limits via `max_x_hops` parameter
- **Direction Control:** Separately control upstream vs downstream traversal

**Semantic Direction:**
- `upstream`: Follow edges toward data sources
- `downstream`: Follow edges toward data consumers
- `both`: Traverse in both directions

**Examples:**
- `Dataset → Job → Dataset` (dataset-level ETL lineage)
- `Attribute → DataDependency → Attribute` (column-level transformations)
- `Dataset → Job → ModelVersion` (training lineage)
- `ModelVersion → Job → Dataset` (inference/prediction lineage)

---

### Y-Axis: Hierarchy

**Purpose:** Navigates parent-child and versioning relationships.

**Constraints:**
- **Depth:** Unlimited - walk complete hierarchy trees
- **Hop Limits:** Separate limits for up (`max_y_hops_up`) and down (`max_y_hops_down`)
- **Sibling Blocking:** Direction commitment prevents cross-branch traversal

**Semantic Direction:**
- `up`: Follow edges toward container/parent nodes
- `down`: Follow edges toward contained/child nodes
- `both`: Traverse in both directions

**Examples:**
- `Attribute → Dataset` (attribute belongs to dataset)
- `AgentVersion → AgenticSystemVersion → AgenticSystem` (versioning hierarchy)
- `BusinessTerm → Glossary` (term belongs to glossary)
- `Attribute → Report` (report elements)

---

### Z-Axis: Associations

**Purpose:** Discovers related entities across domains that aren't lineage or hierarchy.

**Constraint**: 1-Hop Maximum

*Design Rationale:* Z-axis answers "what else is related to this node?" but not "what's related to the related things?" Without this constraint, association-of-association would fan out across the entire graph.

**Exception**: Transformer Nodes (Jobs & Data Dependencies)

*Rationale:* Infrastructure associations (where jobs run, what services they use) are essential lineage context and should always be visible.

**Semantic Direction:**
- `outgoing`: Follow edges where current node is source
- `incoming`: Follow edges where current node is target
- `both`: Follow edges in either direction

*Use Cases:*
- "What does this agent use?" → `outgoing`
- "What uses this dataset?" → `incoming`

**Examples:**
- `AgentVersion → Dataset` (via USES - agent uses data)
- `AgentVersion → ModelVersion` (via USES - agent uses model)
- `Dataset → UseCase` (dataset serves use case)
- `Job → WorkspaceService` (via RUNS_ON - infrastructure platform)
- `ModelVersion → WorkspaceService` (via DEPLOYED_ON - deployment target)

---

### G-Axis: Governance (Overlay)

**Purpose:** Discovers governance, quality, and compliance relationships as a post-processing overlay.

**Characteristics:**
- Applied AFTER X/Y/Z traversal completes
- Never part of BFS exploration
- Results stored separately in `g_nodes` and `g_edges` arrays

**Examples:**
- `Dataset → Dataset:resultset` (data quality results)
- `Dataset:resultset → Report` (quality reporting)
- `UseCase → Guardrail` (compliance controls)

*Design Rationale:* G-axis provides context about governance controls for the in-scope lineage, not a separate governance graph to explore.


## Traversal Algorithm

The engine uses **Breadth-First Search (BFS)** with per-path state tracking to enforce multi-axis constraints while exploring all valid paths simultaneously.

### Algorithm Pseudocode

To traverse the graph starting from a given node:

1. Begin at the start node with a clean state.

2. Place this starting state into a processing queue.

3. While there are still states to process:
   a. Take the next state from the queue.
   b. Find all valid neighbors of the current node.
   c. For each valid neighbor:
      i.   Update the state:
           - If this step is along the Z-axis, increment the Z-hop count.
           - If this step is along the Y-axis, lock in the Y direction (up or down).
           - If this step is upstream on the X-axis, flag that upstream travel has occurred.
           - If this step is upward on the Y-axis, flag that parent travel has occurred.
      ii.  Check whether we've already visited this neighbor under an equivalent state.
           If so, skip it to avoid redundant work.
      iii. Otherwise, record this neighbor (node and edge) as visited,
           and add the new state to the queue for further exploration.

4. Optionally, after traversal is complete, enrich the result
   by attaching governance-layer nodes and edges.

5. Return all discovered nodes, edges, paths, and any governance data.


### Constraint Enforcement (get_neighbors)

To find valid neighbors of the current node:

1. Query the graph for all edges connected to the current node.

2. For each connected edge:
   a. Classify the edge using the taxonomy — this determines which axis
      it belongs to (X, Y, or Z) and its semantic direction.

   b. AXIS FILTER: If this edge's axis is not one of the axes the user asked to traverse, skip it.

   c. Apply Z-AXIS RULES

   d. Apply Y-AXIS RULES

   e. DIRECTION FILTER: Check whether this edge's direction matches what the user requested.

   f. HOP LIMIT CHECK: If accepting this edge would exceed the maximum number of hops allowed on its axis, skip it.

   g. If the edge passes all of the above checks, include the neighbor in the valid set.

3. Return all valid neighbors.

### Performance Characteristics

- **Time Complexity:** O(V + E) where V = nodes, E = edges
- **Space Complexity:** O(V × A) where A = enabled axes (bounded since Z=1)
- **Practical:** Linear in graph size due to Z-axis constraint

**Why Per-Path State?**
- Each path maintains independent constraint counters (`z_hops_taken`, `y_direction_committed`, etc.)
- Allows Z-axis from one path while blocking it in another
- State key: `(node_id, z_hops, axis, y_direction, has_upstream, has_parent)`
- Prevents infinite loops while allowing multiple discovery paths

## Edge Taxonomy System

The taxonomy (`metamodel/edge_taxonomy.yaml`) is the single source of truth for:
- Axis classification (X, Y, Z, G)
- Semantic direction (upstream/downstream, up/down)
- Node roles (resource, transformer, structural, etc.)
- Visibility and hop grouping rules

### Classification Process

To classify a given edge:

1. Load the edge taxonomy file

2. For each entry in the taxonomy:
   a. Check whether the entry matches the edge in question

   b. If a match is found, return the classification

3. If no taxonomy entry matches the edge, it is unclassified
   and should be excluded from traversal.

## Performance

| Metric | Full Traversal | 
|--------|----------------|
| **Time** | O(V + E) |
| **Space** | O(V) | 
| **Practical** | Linear in graph size | 

**Tested Scale:** 910 nodes, 953 relationships across 14 domains

**Optimizations:**
- Hop collapsing for X-axis (Resource → Transformer → Resource = 1 logical hop)
- State-based deduplication prevents redundant traversals
- Z-axis constraint (max 1 hop) prevents exponential explosion

---

## Known Limitations

1. **No cycle detection in Y/X axes**
   - BFS will explore cycles until max_depth
   - Cycles are rare in well-formed lineage graphs

2. **Sub-type matching is exact**
   - No inheritance or fuzzy matching
   - Must explicitly list all allowed sub_types

3. **Edge taxonomy must be manually maintained**
   - No automatic axis inference
   - Schema changes require taxonomy updates

4. **No path ranking**
   - All valid paths are returned equally
   - No shortest-path prioritization

---

## API Endpoints

The implementation exposes two FastAPI endpoints for lineage traversal:

### Full Traversal API

**Endpoint:** `POST /api/lineage/traverse`

**Request:**
```json
{
  "start_node_id": "ds-002",
  "axes": ["x", "y", "z"],
  "x_direction": "both",
  "y_direction": "both",
  "z_direction": "both",
  "max_x_hops": null,
  "max_y_hops_up": null,
  "max_y_hops_down": null,
  "max_z_hops": 1,
  "max_depth": 10,
  "include_transformers": true,
  "include_governance": false
}
```

**Response:**
```json
{
  "start_node": {...},
  "nodes": [...],
  "edges": [...],
  "paths": [...],
  "traversal_metadata": {
    "total_nodes_visited": 43,
    "total_edges_traversed": 58,
    "z_hops_taken": 1,
    "blocked_z_of_z_paths": 0,
    "total_g_nodes": 5,
    "total_g_edges": 7
  },
  "g_nodes": [...],
  "g_edges": [...]
}
```

**Use cases:**
- Complete lineage graph visualization
- Impact analysis
- Full dependency tracking

