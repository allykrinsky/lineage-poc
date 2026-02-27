"""FastAPI backend for Neo4j graph visualization."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
import os
import sys
import logging

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.traversal.taxonomy import EdgeTaxonomy
from src.traversal.engine import TraversalEngine
from src.traversal.hop_collapsing import HopCollapser
from pathlib import Path
from backend.models import (
    TraversalRequest,
    TraversalResponse,
    NodeResponse,
    EdgeResponse,
    PathResponse,
    PathStepResponse,
    TraversalMetadata,
    OneHopRequest,
    OneHopResponse,
    NeighborEntry,
    OneHopAxisNeighbors,
    OneHopYAxisNeighbors,
    OneHopZAxisNeighbors,
    OneHopGAxisNeighbors,
    OneHopMetadata
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Neo4j configuration
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")

app = FastAPI(title="Graph Analytics API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Neo4j driver
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# Load edge taxonomy for traversal engine
taxonomy_path = Path(__file__).parent.parent / "metamodel" / "edge_taxonomy.yaml"
edge_taxonomy = EdgeTaxonomy(taxonomy_path)
hop_collapser = HopCollapser(edge_taxonomy)


class Node(BaseModel):
    id: str
    label: str
    properties: Dict[str, Any]


class Edge(BaseModel):
    source: str
    target: str
    type: str
    properties: Optional[Dict[str, Any]] = {}


class GraphData(BaseModel):
    nodes: List[Node]
    edges: List[Edge]


def format_node(record) -> Dict[str, Any]:
    """Format a Neo4j node for the API response."""
    node = record["n"]
    labels = list(node.labels)
    props = dict(node)

    return {
        "id": props.get("id", str(node.id)),
        "label": labels[0] if labels else "Unknown",
        "properties": props
    }


def format_relationship(record) -> Dict[str, Any]:
    """Format a Neo4j relationship for the API response."""
    rel = record["r"]
    source_node = record["source"]
    target_node = record["target"]

    return {
        "source": source_node["id"] if "id" in source_node else str(source_node.id),
        "target": target_node["id"] if "id" in target_node else str(target_node.id),
        "type": rel.type,
        "properties": dict(rel)
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Graph Analytics API",
        "version": "1.0.0",
        "endpoints": {
            "/api/graph": "Get entire graph",
            "/api/graph/nodes": "Get all nodes",
            "/api/graph/edges": "Get all edges",
            "/api/graph/node/{node_id}": "Get node by ID with neighbors",
            "/api/graph/search?q={query}": "Search nodes by property values",
            "/api/lineage/traverse": "Multi-axis lineage traversal with Z-hop constraints (POST)",
            "/api/lineage/one-hop": "Get immediate neighbors grouped by axis and direction (POST)"
        }
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    try:
        with driver.session() as session:
            result = session.run("RETURN 1 as health")
            result.single()
        return {"status": "healthy", "neo4j": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Neo4j connection failed: {str(e)}")


@app.get("/api/graph", response_model=GraphData)
async def get_graph(limit: int = 100):
    """Get the entire graph (nodes and relationships)."""
    try:
        with driver.session() as session:
            # Get nodes
            nodes_result = session.run(f"""
                MATCH (n)
                RETURN n
                LIMIT {limit}
            """)
            nodes = [format_node(record) for record in nodes_result]

            # Get node IDs for filtering relationships
            node_ids = [node["id"] for node in nodes]

            # Get relationships between the fetched nodes
            rels_result = session.run("""
                MATCH (source)-[r]->(target)
                WHERE source.id IN $node_ids AND target.id IN $node_ids
                RETURN r, source, target
            """, {"node_ids": node_ids})

            edges = [format_relationship(record) for record in rels_result]

        return GraphData(nodes=nodes, edges=edges)

    except Exception as e:
        logger.error(f"Error fetching graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph/nodes")
async def get_nodes(limit: int = 100, label: Optional[str] = None):
    """Get all nodes, optionally filtered by label."""
    try:
        with driver.session() as session:
            if label:
                query = f"""
                    MATCH (n:{label})
                    RETURN n
                    LIMIT {limit}
                """
            else:
                query = f"""
                    MATCH (n)
                    RETURN n
                    LIMIT {limit}
                """

            result = session.run(query)
            nodes = [format_node(record) for record in result]

        return {"nodes": nodes}

    except Exception as e:
        logger.error(f"Error fetching nodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph/edges")
async def get_edges(limit: int = 100, relationship_type: Optional[str] = None):
    """Get all edges, optionally filtered by relationship type."""
    try:
        with driver.session() as session:
            if relationship_type:
                query = f"""
                    MATCH (source)-[r:{relationship_type}]->(target)
                    RETURN r, source, target
                    LIMIT {limit}
                """
            else:
                query = f"""
                    MATCH (source)-[r]->(target)
                    RETURN r, source, target
                    LIMIT {limit}
                """

            result = session.run(query)
            edges = [format_relationship(record) for record in result]

        return {"edges": edges}

    except Exception as e:
        logger.error(f"Error fetching edges: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph/node/{node_id}")
async def get_node_with_neighbors(node_id: str, depth: int = 1):
    """Get a node and its neighbors up to a specified depth."""
    try:
        with driver.session() as session:
            # Get the node and its neighbors
            query = f"""
                MATCH path = (n {{id: $node_id}})-[*1..{depth}]-(neighbor)
                WITH n, collect(DISTINCT neighbor) as neighbors,
                     [r in relationships(path) | r] as rels
                RETURN n, neighbors, rels
            """

            result = session.run(query, {"node_id": node_id})
            record = result.single()

            if not record:
                raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

            # Format nodes
            nodes = [format_node({"n": record["n"]})]
            for neighbor in record["neighbors"]:
                nodes.append(format_node({"n": neighbor}))

            # Format relationships
            edges = []
            for rel in record["rels"]:
                edges.append({
                    "source": rel.start_node["id"] if "id" in rel.start_node else str(rel.start_node.id),
                    "target": rel.end_node["id"] if "id" in rel.end_node else str(rel.end_node.id),
                    "type": rel.type,
                    "properties": dict(rel)
                })

        return GraphData(nodes=nodes, edges=edges)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching node {node_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph/search")
async def search_nodes(q: str, limit: int = 50):
    """Search nodes by property values."""
    try:
        with driver.session() as session:
            # Search across common text properties
            query = """
                MATCH (n)
                WHERE
                    toLower(toString(n.id)) CONTAINS toLower($query)
                    OR toLower(toString(n.title)) CONTAINS toLower($query)
                    OR toLower(toString(n.name)) CONTAINS toLower($query)
                    OR toLower(toString(n.description)) CONTAINS toLower($query)
                RETURN n
                LIMIT $limit
            """

            result = session.run(query, {"query": q, "limit": limit})
            nodes = [format_node(record) for record in result]

        return {"nodes": nodes, "query": q}

    except Exception as e:
        logger.error(f"Error searching nodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph/stats")
async def get_graph_stats():
    """Get graph statistics."""
    try:
        with driver.session() as session:
            # Count nodes by label
            labels_result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as label, count(*) as count
                ORDER BY count DESC
            """)
            labels = [{"label": record["label"], "count": record["count"]}
                     for record in labels_result]

            # Count relationships by type
            rels_result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(*) as count
                ORDER BY count DESC
            """)
            relationships = [{"type": record["type"], "count": record["count"]}
                           for record in rels_result]

            # Total counts
            total_nodes = sum(item["count"] for item in labels)
            total_rels = sum(item["count"] for item in relationships)

        return {
            "total_nodes": total_nodes,
            "total_relationships": total_rels,
            "node_labels": labels,
            "relationship_types": relationships
        }

    except Exception as e:
        logger.error(f"Error fetching graph stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/graph/lineage/{node_id}")
async def get_lineage(node_id: str, direction: str = "both"):
    """
    Get lineage (upstream and/or downstream) for a specific node.

    Args:
        node_id: The ID of the node to get lineage for
        direction: "upstream", "downstream", or "both"
    """
    try:
        with driver.session() as session:
            if direction == "upstream":
                query = """
                    MATCH path = (ancestor)-[*]->(n {id: $node_id})
                    WITH n, collect(DISTINCT ancestor) as ancestors,
                         [r in relationships(path) | r] as rels
                    RETURN n, ancestors, rels
                """
            elif direction == "downstream":
                query = """
                    MATCH path = (n {id: $node_id})-[*]->(descendant)
                    WITH n, collect(DISTINCT descendant) as descendants,
                         [r in relationships(path) | r] as rels
                    RETURN n, descendants as ancestors, rels
                """
            else:  # both
                query = """
                    MATCH path = (n {id: $node_id})-[*]-(related)
                    WITH n, collect(DISTINCT related) as ancestors,
                         [r in relationships(path) | r] as rels
                    RETURN n, ancestors, rels
                """

            result = session.run(query, {"node_id": node_id})
            record = result.single()

            if not record:
                raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

            # Format nodes
            nodes = [format_node({"n": record["n"]})]
            for ancestor in record.get("ancestors", []):
                nodes.append(format_node({"n": ancestor}))

            # Format relationships
            edges = []
            for rel in record.get("rels", []):
                edges.append({
                    "source": rel.start_node["id"] if "id" in rel.start_node else str(rel.start_node.id),
                    "target": rel.end_node["id"] if "id" in rel.end_node else str(rel.end_node.id),
                    "type": rel.type,
                    "properties": dict(rel)
                })

        return GraphData(nodes=nodes, edges=edges)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching lineage for {node_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@app.post("/api/lineage/traverse", response_model=TraversalResponse)
async def traverse_lineage(request: TraversalRequest):
    """
    Traverse the graph using multi-axis lineage constraints.

    This endpoint supports:
    - X-axis (lineage): upstream/downstream data flow
    - Y-axis (hierarchy): up/down organizational structure
    - Z-axis (association): cross-cutting relationships (max 1 hop)
    - G-axis (governance overlay): 1-hop Dataset:resultset + Guardrail nodes
      attached to any in-scope X/Y/Z node (set include_governance=true)

    The key constraint: Z-of-Z traversal is blocked. After taking a Z-hop,
    further Z-hops are prevented, but X and Y traversal can continue.
    G-axis is a post-processing overlay; it never changes X/Y/Z scope.
    """
    try:
        # Create traversal engine
        with TraversalEngine(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, edge_taxonomy) as engine:
            # Execute traversal
            result = engine.traverse(
                start_node_id=request.start_node_id,
                axes=request.axes,
                x_direction=request.x_direction,
                y_direction=request.y_direction,
                z_direction=request.z_direction,
                max_x_hops=request.max_x_hops,
                max_y_hops_up=request.max_y_hops_up,
                max_y_hops_down=request.max_y_hops_down,
                max_z_hops=request.max_z_hops,
                max_depth=request.max_depth,
                include_transformers=request.include_transformers,
                include_governance=request.include_governance
            )

            # Convert nodes to response format
            nodes_response = [
                NodeResponse(
                    id=node['id'],
                    type=node['type'],
                    properties={k: v for k, v in node.items() if k not in ['id', 'type']}
                )
                for node in result.nodes
            ]

            # Convert edges to response format
            edges_response = [
                EdgeResponse(
                    type=edge['type'],
                    source=edge['source'],
                    target=edge['target'],
                    properties=edge.get('properties', {})
                )
                for edge in result.edges
            ]

            # Collapse X-axis hops if requested
            collapsed_paths = hop_collapser.collapse_paths(result.paths, result.nodes)

            # Convert paths to response format
            paths_response = []
            for path_info in collapsed_paths:
                if 'logical_steps' in path_info:
                    # X-axis path with hop collapsing
                    steps = []
                    for step in path_info['logical_steps']:
                        step_response = PathStepResponse(
                            from_node=NodeResponse(
                                id=step['from']['id'],
                                type=step['from']['type'],
                                properties={k: v for k, v in step['from'].items() if k not in ['id', 'type']}
                            ),
                            to_node=NodeResponse(
                                id=step['to']['id'],
                                type=step['to']['type'],
                                properties={k: v for k, v in step['to'].items() if k not in ['id', 'type']}
                            ),
                            via_node=NodeResponse(
                                id=step['via']['id'],
                                type=step['via']['type'],
                                properties={k: v for k, v in step['via'].items() if k not in ['id', 'type']}
                            ) if step.get('via') else None,
                            hop_group=step.get('hop_group'),
                            edge_names=step['edge_names']
                        )
                        steps.append(step_response)

                    paths_response.append(PathResponse(
                        axis=path_info['axis'],
                        logical_steps=steps,
                        z_hops=path_info.get('z_hops', 0)
                    ))
                else:
                    # Y or Z axis path (no hop collapsing)
                    paths_response.append(PathResponse(
                        axis=path_info['axis'],
                        logical_steps=[],
                        z_hops=path_info.get('z_hops', 0)
                    ))

            # Convert G-axis governance nodes/edges (populated when include_governance=True)
            g_nodes_response = [
                NodeResponse(
                    id=node['id'],
                    type=node['type'],
                    properties={k: v for k, v in node.items() if k not in ['id', 'type']}
                )
                for node in result.g_nodes
            ]
            g_edges_response = [
                EdgeResponse(
                    type=edge['type'],
                    source=edge['source'],
                    target=edge['target'],
                    properties=edge.get('properties', {})
                )
                for edge in result.g_edges
            ]

            # Build response
            return TraversalResponse(
                start_node=NodeResponse(
                    id=result.start_node['id'],
                    type=result.start_node['type'],
                    properties={k: v for k, v in result.start_node.items() if k not in ['id', 'type']}
                ),
                nodes=nodes_response,
                edges=edges_response,
                paths=paths_response,
                traversal_metadata=TraversalMetadata(
                    total_nodes_visited=result.metadata.get('total_nodes_visited', 0),
                    total_edges_traversed=result.metadata.get('total_edges_traversed', 0),
                    z_hops_taken=max((p.get('z_hops', 0) for p in collapsed_paths), default=0),
                    blocked_z_of_z_paths=0  # TODO: track this in engine
                ),
                g_nodes=g_nodes_response,
                g_edges=g_edges_response
            )

    except ValueError as e:
        logger.error(f"Invalid traversal request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error during traversal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/lineage/one-hop", response_model=OneHopResponse)
async def one_hop_neighbors(request: OneHopRequest):
    """
    Get immediate neighbors (1-hop) from a node, grouped by axis and direction.

    This endpoint provides a "what's directly connected?" view following the same
    traversal rules as the full traverse method, but limited to 1 hop.

    Features:
    - X-axis neighbors grouped by upstream/downstream
    - Y-axis neighbors grouped by up/down
    - Z-axis neighbors (no direction, since associations are bidirectional)
    - G-axis governance neighbors: Dataset:resultset and Guardrail nodes reachable
      via 1-hop governable edges (always returned by default, set include_governance=false to skip)
    - Same axis constraints as full traversal (Z-axis available from base node)

    Use cases:
    - UI navigation and autocomplete
    - Quick exploration of connected entities
    - Building interactive graph UIs with governance overlay
    """
    try:
        # Create traversal engine
        with TraversalEngine(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, edge_taxonomy) as engine:
            # Execute one-hop query
            result = engine.one_hop(
                start_node_id=request.start_node_id,
                axes=request.axes,
                z_direction=request.z_direction,
                include_governance=request.include_governance
            )

            # Helper function to convert neighbor entries
            def convert_neighbor_entry(entry: Dict[str, Any]) -> NeighborEntry:
                node_data = entry['node']
                edge_data = entry['edge']

                return NeighborEntry(
                    node=NodeResponse(
                        id=node_data['id'],
                        type=node_data['type'],
                        properties={k: v for k, v in node_data.items() if k not in ['id', 'type']}
                    ),
                    edge=EdgeResponse(
                        type=edge_data['type'],
                        source=edge_data['source'],
                        target=edge_data['target'],
                        properties=edge_data.get('properties', {})
                    ),
                    edge_type=entry['edge_type'],
                    axis=entry['axis']
                )

            # Convert X-axis neighbors
            x_axis_response = OneHopAxisNeighbors(
                upstream=[convert_neighbor_entry(e) for e in result.x_axis['upstream']],
                downstream=[convert_neighbor_entry(e) for e in result.x_axis['downstream']]
            )

            # Convert Y-axis neighbors
            y_axis_response = OneHopYAxisNeighbors(
                up=[convert_neighbor_entry(e) for e in result.y_axis['up']],
                down=[convert_neighbor_entry(e) for e in result.y_axis['down']]
            )

            # Convert Z-axis neighbors (bucketed by outgoing/incoming)
            z_axis_response = OneHopZAxisNeighbors(
                outgoing=[convert_neighbor_entry(e) for e in result.z_axis['outgoing']],
                incoming=[convert_neighbor_entry(e) for e in result.z_axis['incoming']]
            )

            # Convert G-axis governance neighbors (bucketed by outgoing/incoming)
            g_axis_response = OneHopGAxisNeighbors(
                outgoing=[convert_neighbor_entry(e) for e in result.g_axis['outgoing']],
                incoming=[convert_neighbor_entry(e) for e in result.g_axis['incoming']]
            )

            # Build response
            return OneHopResponse(
                start_node=NodeResponse(
                    id=result.start_node['id'],
                    type=result.start_node['type'],
                    properties={k: v for k, v in result.start_node.items() if k not in ['id', 'type']}
                ),
                x_axis=x_axis_response,
                y_axis=y_axis_response,
                z_axis=z_axis_response,
                g_axis=g_axis_response,
                metadata=OneHopMetadata(
                    total_x_upstream=result.metadata['total_x_upstream'],
                    total_x_downstream=result.metadata['total_x_downstream'],
                    total_y_up=result.metadata['total_y_up'],
                    total_y_down=result.metadata['total_y_down'],
                    total_z_outgoing=result.metadata['total_z_outgoing'],
                    total_z_incoming=result.metadata['total_z_incoming'],
                    total_z=result.metadata['total_z'],
                    total_g_outgoing=result.metadata.get('total_g_outgoing', 0),
                    total_g_incoming=result.metadata.get('total_g_incoming', 0),
                    total_g=result.metadata.get('total_g', 0)
                )
            )

    except ValueError as e:
        logger.error(f"Invalid one-hop request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error during one-hop query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("shutdown")
async def shutdown_event():
    """Close Neo4j driver on shutdown."""
    driver.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
