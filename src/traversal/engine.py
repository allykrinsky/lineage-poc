"""
Graph Traversal Engine

Implements BFS traversal with multi-axis constraints for lineage queries.
Key feature: Z-axis limited to 1 hop per path (no Z-of-Z).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from collections import deque
from neo4j import GraphDatabase
from .taxonomy import EdgeTaxonomy, Axis, SemanticDirection


@dataclass
class TraversalState:
    """State tracking for a single path during BFS traversal"""
    node_id: str
    node_type: str
    node_sub_type: Optional[str]
    path: List[str]  # Node IDs in the path
    z_hops_taken: int  # Number of Z-axis hops taken in this path
    last_axis: Optional[Axis]  # Which axis was used to reach this node
    depth: int  # Total traversal depth
    path_edges: List[Dict]  # Edge information for this path


@dataclass
class TraversalResult:
    """Result of a traversal operation"""
    start_node: Dict
    nodes: List[Dict]
    edges: List[Dict]
    paths: List[Dict]
    metadata: Dict


class TraversalEngine:
    """
    Core traversal engine with multi-axis support and Z-hop constraints.

    The engine uses BFS with per-path state tracking to enforce:
    - X-axis: unlimited depth, follows lineage chains
    - Y-axis: unlimited depth, follows hierarchy
    - Z-axis: max 1 hop per path (Z-of-Z is blocked)
    """

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str, taxonomy: EdgeTaxonomy):
        """
        Initialize traversal engine.

        Args:
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            taxonomy: Loaded edge taxonomy configuration
        """
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.taxonomy = taxonomy

    def close(self):
        """Close Neo4j driver"""
        self.driver.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def traverse(
        self,
        start_node_id: str,
        axes: List[str] = None,
        x_direction: str = "both",
        y_direction: str = "both",
        max_z_hops: int = 1,
        max_depth: Optional[int] = None,
        include_transformers: bool = True
    ) -> TraversalResult:
        """
        Traverse the graph starting from a node.

        Args:
            start_node_id: ID of the starting node
            axes: List of axes to traverse ['x', 'y', 'z'] or subset
            x_direction: 'upstream', 'downstream', or 'both'
            y_direction: 'up', 'down', or 'both'
            max_z_hops: Maximum Z-axis hops per path (default 1)
            max_depth: Optional global depth limit
            include_transformers: Whether to include transformer nodes in results

        Returns:
            TraversalResult with nodes, edges, and path information
        """
        if axes is None:
            axes = ['x', 'y', 'z']

        axes = [Axis(a) for a in axes]

        with self.driver.session() as session:
            # Get start node info
            start_node = self._get_node(session, start_node_id)
            if not start_node:
                raise ValueError(f"Start node {start_node_id} not found")

            # Initialize BFS
            visited_nodes = {}  # node_id -> node_dict
            visited_edges = {}  # edge_id -> edge_dict
            all_paths = []

            queue = deque([TraversalState(
                node_id=start_node['id'],
                node_type=start_node['type'],
                node_sub_type=start_node.get('sub_type'),
                path=[start_node['id']],
                z_hops_taken=0,
                last_axis=None,
                depth=0,
                path_edges=[]
            )])

            visited_nodes[start_node['id']] = start_node

            # Track visited states to avoid infinite loops
            # Key: (node_id, z_hops_taken, last_axis)
            visited_states = set()
            visited_states.add((start_node['id'], 0, None))

            # BFS traversal
            while queue:
                current_state = queue.popleft()

                # Check depth limit
                if max_depth and current_state.depth >= max_depth:
                    continue

                # Get all outgoing and incoming edges
                neighbors = self._get_neighbors(
                    session,
                    current_state.node_id,
                    current_state.node_type,
                    current_state.node_sub_type,
                    axes,
                    x_direction,
                    y_direction,
                    current_state.z_hops_taken,
                    max_z_hops
                )

                for neighbor_info in neighbors:
                    neighbor_node = neighbor_info['node']
                    edge = neighbor_info['edge']
                    edge_axis = neighbor_info['axis']
                    edge_classification = neighbor_info['classification']

                    neighbor_id = neighbor_node['id']

                    # Calculate new Z-hop count
                    new_z_hops = current_state.z_hops_taken
                    if edge_axis == Axis.Z:
                        new_z_hops += 1

                    # Create state key to avoid revisiting same state
                    state_key = (neighbor_id, new_z_hops, edge_axis)

                    # Skip if we've already visited this state
                    if state_key in visited_states:
                        continue

                    visited_states.add(state_key)

                    # Track node and edge
                    if neighbor_id not in visited_nodes:
                        visited_nodes[neighbor_id] = neighbor_node

                    edge_id = edge.get('id', f"{edge['source']}-{edge['type']}-{edge['target']}")
                    if edge_id not in visited_edges:
                        visited_edges[edge_id] = edge

                    # Create new path state
                    new_path = current_state.path + [neighbor_id]
                    new_path_edges = current_state.path_edges + [{
                        'edge': edge,
                        'axis': edge_axis.value,
                        'classification': edge_classification
                    }]

                    new_state = TraversalState(
                        node_id=neighbor_id,
                        node_type=neighbor_node['type'],
                        node_sub_type=neighbor_node.get('sub_type'),
                        path=new_path,
                        z_hops_taken=new_z_hops,
                        last_axis=edge_axis,
                        depth=current_state.depth + 1,
                        path_edges=new_path_edges
                    )

                    queue.append(new_state)

                    # Record path
                    all_paths.append({
                        'path': new_path,
                        'edges': new_path_edges,
                        'axis': edge_axis.value,
                        'z_hops': new_z_hops
                    })

            # Build result
            return TraversalResult(
                start_node=start_node,
                nodes=list(visited_nodes.values()),
                edges=list(visited_edges.values()),
                paths=all_paths,
                metadata={
                    'total_nodes_visited': len(visited_nodes),
                    'total_edges_traversed': len(visited_edges),
                    'total_paths': len(all_paths),
                    'max_z_hops': max_z_hops
                }
            )

    def _get_node(self, session, node_id: str) -> Optional[Dict]:
        """Fetch a node by ID from Neo4j"""
        result = session.run(
            """
            MATCH (n {id: $node_id})
            RETURN n, labels(n)[0] as label
            """,
            node_id=node_id
        )
        record = result.single()
        if not record:
            return None

        node = dict(record['n'])
        node['type'] = self._normalize_node_type(record['label'])
        return node

    def _normalize_node_type(self, label: str) -> str:
        """Normalize Neo4j label to taxonomy node type (lowercase)"""
        # Convert from Neo4j label format (e.g., "Dataset") to taxonomy format (e.g., "dataset")
        # Handle special cases
        label_lower = label.lower()

        # Map common variations
        mappings = {
            'etljob': 'etl_job',
            'datadependency': 'data_dependency',
            'dataflow': 'data_flow',
            'modelversion': 'model_version',
            'agentversion': 'agent_version',
            'agenticsystem': 'agentic_system',
            'agenticsystemversion': 'agentic_system_version',
            'mcpserver': 'mcp_server',
            'mcpresource': 'mcp_resource',
            'mcptool': 'mcp_tool',
            'workspaceservice': 'workspace_service',
            'usecase': 'use_case',
            'dataconcept': 'data_concept'
        }

        return mappings.get(label_lower, label_lower)

    def _get_neighbors(
        self,
        session,
        node_id: str,
        node_type: str,
        node_sub_type: Optional[str],
        axes: List[Axis],
        x_direction: str,
        y_direction: str,
        current_z_hops: int,
        max_z_hops: int
    ) -> List[Dict]:
        """
        Get all valid neighbors of a node based on traversal parameters.

        Returns list of dicts with keys: node, edge, axis, classification
        """
        neighbors = []

        # Get all edges (both directions)
        result = session.run(
            """
            MATCH (n {id: $node_id})-[r]-(m)
            RETURN n, r, m,
                   labels(n)[0] as n_label,
                   labels(m)[0] as m_label,
                   type(r) as edge_type,
                   startNode(r) = n as is_outgoing
            """,
            node_id=node_id
        )

        for record in result:
            edge_type = record['edge_type']
            is_outgoing = record['is_outgoing']

            # Get node labels and properties
            source_node = dict(record['n'] if is_outgoing else record['m'])
            target_node = dict(record['m'] if is_outgoing else record['n'])
            source_type = self._normalize_node_type(record['n_label'] if is_outgoing else record['m_label'])
            target_type = self._normalize_node_type(record['m_label'] if is_outgoing else record['n_label'])

            source_sub_type = source_node.get('sub_type')
            target_sub_type = target_node.get('sub_type')

            # Classify the edge
            classification = self.taxonomy.classify_edge(
                edge_type,
                source_type,
                target_type,
                source_sub_type,
                target_sub_type
            )

            if not classification:
                # Edge not in taxonomy, skip
                continue

            # Check if this axis is enabled
            if classification.axis not in axes:
                continue

            # Check Z-hop constraint
            if classification.axis == Axis.Z:
                if current_z_hops >= max_z_hops:
                    # Already taken max Z-hops, cannot continue on Z
                    continue

            # Check direction constraints
            should_traverse = self._should_traverse_edge(
                classification,
                is_outgoing,
                x_direction,
                y_direction
            )

            if not should_traverse:
                continue

            # Build neighbor info
            neighbor_node = target_node if is_outgoing else source_node
            neighbor_node['type'] = target_type if is_outgoing else source_type

            edge_dict = {
                'type': edge_type,
                'source': source_node['id'],
                'target': target_node['id'],
                'properties': dict(record['r'])
            }

            neighbors.append({
                'node': neighbor_node,
                'edge': edge_dict,
                'axis': classification.axis,
                'classification': classification
            })

        return neighbors

    def _should_traverse_edge(
        self,
        classification,
        is_outgoing: bool,
        x_direction: str,
        y_direction: str
    ) -> bool:
        """
        Determine if an edge should be traversed based on direction constraints.

        Args:
            classification: EdgeClassification object
            is_outgoing: Whether we're traversing in the stored edge direction
            x_direction: 'upstream', 'downstream', or 'both'
            y_direction: 'up', 'down', or 'both'

        Returns:
            True if edge should be traversed
        """
        if classification.axis == Axis.X:
            # X-axis: check semantic direction
            semantic_dir = classification.semantic_direction

            if is_outgoing:
                # Following stored direction
                edge_semantic = semantic_dir
            else:
                # Reverse direction
                edge_semantic = (
                    SemanticDirection.DOWNSTREAM
                    if semantic_dir == SemanticDirection.UPSTREAM
                    else SemanticDirection.UPSTREAM
                )

            if x_direction == "both":
                return True
            elif x_direction == "upstream":
                return edge_semantic == SemanticDirection.UPSTREAM
            elif x_direction == "downstream":
                return edge_semantic == SemanticDirection.DOWNSTREAM

        elif classification.axis == Axis.Y:
            # Y-axis: check semantic_up
            semantic_up = classification.semantic_up

            # Determine actual direction based on semantic_up and is_outgoing
            if semantic_up == SemanticDirection.FORWARD:
                # Forward = up
                actual_dir = "up" if is_outgoing else "down"
            else:  # semantic_up == REVERSE
                # Reverse = need to go backwards to go up
                actual_dir = "down" if is_outgoing else "up"

            if y_direction == "both":
                return True
            else:
                return y_direction == actual_dir

        elif classification.axis == Axis.Z:
            # Z-axis: always traverse (constraint is on hop count)
            return True

        return False
