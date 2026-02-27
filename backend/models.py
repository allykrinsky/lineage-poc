"""
Pydantic models for the lineage traversal API.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class TraversalRequest(BaseModel):
    """Request model for lineage traversal"""
    start_node_id: str = Field(..., description="ID of the starting node for traversal")
    axes: List[str] = Field(
        default=["x", "y", "z"],
        description="Axes to traverse: 'x' (lineage), 'y' (hierarchy), 'z' (association)"
    )
    x_direction: str = Field(
        default="both",
        description="X-axis direction: 'upstream', 'downstream', or 'both'"
    )
    y_direction: str = Field(
        default="both",
        description="Y-axis direction: 'up', 'down', or 'both'"
    )
    z_direction: str = Field(
        default="both",
        description="Z-axis direction: 'outgoing' (node is edge source), 'incoming' (node is edge target), or 'both'"
    )
    max_x_hops: Optional[int] = Field(
        default=None,
        description="Maximum number of X-axis hops (lineage steps) in either direction (None = unlimited)"
    )
    max_y_hops_up: Optional[int] = Field(
        default=None,
        description="Maximum number of Y-axis hops to traverse upward in hierarchy (None = unlimited)"
    )
    max_y_hops_down: Optional[int] = Field(
        default=None,
        description="Maximum number of Y-axis hops to traverse downward in hierarchy (None = unlimited)"
    )
    max_z_hops: int = Field(
        default=1,
        description="Maximum Z-axis hops per path (default 1, prevents Z-of-Z)"
    )
    max_depth: Optional[int] = Field(
        default=None,
        description="Optional global depth limit for traversal"
    )
    include_transformers: bool = Field(
        default=True,
        description="Whether to include transformer nodes (jobs, dependencies) in response"
    )
    include_governance: bool = Field(
        default=False,
        description=(
            "When True, apply the G-axis governance overlay after X/Y/Z traversal. "
            "For every in-scope node, exactly 1-hop governable edges are followed to "
            "bring Dataset:resultset and Guardrail nodes into g_nodes/g_edges. "
            "Never changes X/Y/Z scope."
        )
    )

    class Config:
        json_schema_extra = {
            "example": {
                "start_node_id": "ds-002",
                "axes": ["x", "y", "z"],
                "x_direction": "both",
                "y_direction": "both",
                "z_direction": "both",
                "max_x_hops": 10,
                "max_y_hops_up": 10,
                "max_y_hops_down": 10,
                "max_z_hops": 1,
                "max_depth": 10,
                "include_transformers": True,
                "include_governance": False
            }
        }


class NodeResponse(BaseModel):
    """Node in the traversal response"""
    id: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class EdgeResponse(BaseModel):
    """Edge in the traversal response"""
    type: str
    source: str
    target: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class PathStepResponse(BaseModel):
    """A single step in a traversal path"""
    from_node: NodeResponse
    to_node: NodeResponse
    via_node: Optional[NodeResponse] = None
    hop_group: Optional[str] = None
    edge_names: List[str]


class PathResponse(BaseModel):
    """A complete path through the graph"""
    axis: str
    direction: Optional[str] = None
    logical_steps: List[PathStepResponse] = Field(default_factory=list)
    z_hops: int = 0


class TraversalMetadata(BaseModel):
    """Metadata about the traversal operation"""
    z_hops_taken: int = Field(default=0, description="Maximum Z-hops taken in any path")
    total_nodes_visited: int
    total_edges_traversed: int = 0
    blocked_z_of_z_paths: int = Field(
        default=0,
        description="Number of paths blocked due to Z-of-Z constraint"
    )


class TraversalResponse(BaseModel):
    """Response model for lineage traversal"""
    start_node: NodeResponse
    nodes: List[NodeResponse]
    edges: List[EdgeResponse]
    paths: List[PathResponse] = Field(default_factory=list)
    traversal_metadata: TraversalMetadata
    # G-axis governance overlay (empty unless include_governance=True in request)
    g_nodes: List[NodeResponse] = Field(
        default_factory=list,
        description="Governance nodes (Dataset:resultset, Guardrail) reached via 1-hop G-axis edges from any in-scope X/Y/Z node."
    )
    g_edges: List[EdgeResponse] = Field(
        default_factory=list,
        description="G-axis edges connecting in-scope X/Y/Z nodes to their governance nodes."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "start_node": {
                    "id": "ds-002",
                    "type": "dataset",
                    "properties": {
                        "name": "curated_transactions",
                        "description": "Cleaned and enriched transaction data"
                    }
                },
                "nodes": [
                    {
                        "id": "ds-002",
                        "type": "dataset",
                        "properties": {"name": "curated_transactions"}
                    },
                    {
                        "id": "ds-001",
                        "type": "dataset",
                        "properties": {"name": "raw_transactions"}
                    }
                ],
                "edges": [
                    {
                        "type": "DATASET_PRODUCED_BY",
                        "source": "ds-002",
                        "target": "job-001",
                        "properties": {}
                    }
                ],
                "paths": [],
                "traversal_metadata": {
                    "z_hops_taken": 1,
                    "total_nodes_visited": 15,
                    "total_edges_traversed": 18,
                    "blocked_z_of_z_paths": 2
                }
            }
        }


# ============================================================================
# One-Hop API Models
# ============================================================================

class NeighborEntry(BaseModel):
    """A single neighbor with edge information"""
    node: NodeResponse
    edge: EdgeResponse
    edge_type: str
    axis: str


class OneHopAxisNeighbors(BaseModel):
    """Neighbors organized by direction within an axis"""
    upstream: List[NeighborEntry] = Field(default_factory=list)
    downstream: List[NeighborEntry] = Field(default_factory=list)


class OneHopYAxisNeighbors(BaseModel):
    """Y-axis neighbors organized by direction"""
    up: List[NeighborEntry] = Field(default_factory=list)
    down: List[NeighborEntry] = Field(default_factory=list)


class OneHopZAxisNeighbors(BaseModel):
    """Z-axis neighbors organized by edge direction.

    outgoing: edges where the start node is the source (e.g. agent -[uses]-> dataset)
    incoming: edges where the start node is the target (e.g. agent -[uses]-> this dataset)
    """
    outgoing: List[NeighborEntry] = Field(default_factory=list)
    incoming: List[NeighborEntry] = Field(default_factory=list)


class OneHopGAxisNeighbors(BaseModel):
    """G-axis (governance) neighbors — exactly 1 hop, never chained.

    outgoing: governable edges where the start node is the source
              e.g. dataset -[RESULTSETS_DATASET]-> resultset
    incoming: governable edges where the start node is the target
              e.g. guardrail -[GUARDRAIL_USE_CASE]-> use_case  (use_case is target)
    """
    outgoing: List[NeighborEntry] = Field(default_factory=list)
    incoming: List[NeighborEntry] = Field(default_factory=list)


class OneHopMetadata(BaseModel):
    """Metadata for one-hop results"""
    total_x_upstream: int = 0
    total_x_downstream: int = 0
    total_y_up: int = 0
    total_y_down: int = 0
    total_z_outgoing: int = 0
    total_z_incoming: int = 0
    total_z: int = 0
    total_g_outgoing: int = 0
    total_g_incoming: int = 0
    total_g: int = 0


class OneHopRequest(BaseModel):
    """Request model for one-hop neighbor discovery"""
    start_node_id: str = Field(..., description="ID of the node to get neighbors for")
    axes: List[str] = Field(
        default=["x", "y", "z"],
        description="Axes to include: 'x' (lineage), 'y' (hierarchy), 'z' (association)"
    )
    z_direction: str = Field(
        default="both",
        description="Z-axis direction: 'outgoing' (node is edge source), 'incoming' (node is edge target), or 'both'"
    )
    include_governance: bool = Field(
        default=True,
        description=(
            "When True (default), include G-axis governance neighbors: "
            "Dataset:resultset and Guardrail nodes reachable via 1-hop governable edges."
        )
    )

    class Config:
        json_schema_extra = {
            "example": {
                "start_node_id": "ds-002",
                "axes": ["x", "y", "z"],
                "z_direction": "both",
                "include_governance": True
            }
        }


class OneHopResponse(BaseModel):
    """Response model for one-hop neighbor discovery"""
    start_node: NodeResponse
    x_axis: OneHopAxisNeighbors
    y_axis: OneHopYAxisNeighbors
    z_axis: OneHopZAxisNeighbors
    g_axis: OneHopGAxisNeighbors = Field(
        default_factory=OneHopGAxisNeighbors,
        description="Governance neighbors (Dataset:resultset, Guardrail) reachable via 1-hop G-axis edges."
    )
    metadata: OneHopMetadata

    class Config:
        json_schema_extra = {
            "example": {
                "start_node": {
                    "id": "ds-002",
                    "type": "dataset",
                    "properties": {
                        "name": "curated_transactions",
                        "description": "Cleaned and enriched transaction data"
                    }
                },
                "x_axis": {
                    "upstream": [
                        {
                            "node": {
                                "id": "job-001",
                                "type": "job",
                                "properties": {"name": "ingest_raw_transactions"}
                            },
                            "edge": {
                                "type": "DATASET_PRODUCED_BY",
                                "source": "ds-002",
                                "target": "job-001",
                                "properties": {}
                            },
                            "edge_type": "DATASET_PRODUCED_BY",
                            "axis": "x"
                        }
                    ],
                    "downstream": [
                        {
                            "node": {
                                "id": "job-002",
                                "type": "job",
                                "properties": {"name": "build_fraud_features"}
                            },
                            "edge": {
                                "type": "IS_CONSUMED_BY",
                                "source": "ds-002",
                                "target": "job-002",
                                "properties": {}
                            },
                            "edge_type": "IS_CONSUMED_BY",
                            "axis": "x"
                        }
                    ]
                },
                "y_axis": {
                    "up": [],
                    "down": [
                        {
                            "node": {
                                "id": "attr-001",
                                "type": "attribute",
                                "properties": {"name": "account_id"}
                            },
                            "edge": {
                                "type": "IS_ATTRIBUTE_FOR",
                                "source": "attr-001",
                                "target": "ds-002",
                                "properties": {}
                            },
                            "edge_type": "IS_ATTRIBUTE_FOR",
                            "axis": "y"
                        }
                    ]
                },
                "z_axis": [
                    {
                        "node": {
                            "id": "ws-001",
                            "type": "workspace",
                            "properties": {"name": "fraud_detection_workspace"}
                        },
                        "edge": {
                            "type": "WORKSPACE_DATASET",
                            "source": "ws-001",
                            "target": "ds-002",
                            "properties": {}
                        },
                        "edge_type": "WORKSPACE_DATASET",
                        "axis": "z"
                    }
                ],
                "metadata": {
                    "total_x_upstream": 1,
                    "total_x_downstream": 1,
                    "total_y_up": 0,
                    "total_y_down": 1,
                    "total_z": 1
                }
            }
        }
