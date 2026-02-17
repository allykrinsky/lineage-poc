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
    y_direction_committed: Optional[str]  # 'up', 'down', or None - prevents sibling traversal
    has_gone_upstream: bool  # Whether we've taken any upstream edge in this path
    has_gone_to_parent: bool  # Whether we've gone "up" to a parent node via Y-axis


@dataclass
class TraversalResult:
    """Result of a traversal operation"""
    start_node: Dict
    nodes: List[Dict]
    edges: List[Dict]
    paths: List[Dict]
    metadata: Dict


@dataclass
class OneHopResult:
    """Result of a 1-hop traversal showing immediate neighbors by axis"""
    start_node: Dict
    x_axis: Dict[str, List[Dict]]  # {"upstream": [...], "downstream": [...]}
    y_axis: Dict[str, List[Dict]]  # {"up": [...], "down": [...]}
    z_axis: Dict[str, List[Dict]]  # {"outgoing": [...], "incoming": [...]}
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
        z_direction: str = "both",
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
            z_direction: 'outgoing' (follow edges where node is source),
                         'incoming' (follow edges where node is target), or 'both'
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
                path_edges=[],
                y_direction_committed=None,  # No Y-direction committed yet at base node
                has_gone_upstream=False,  # Start node hasn't gone upstream
                has_gone_to_parent=False  # Start node hasn't gone to parent
            )])

            visited_nodes[start_node['id']] = start_node

            # Track visited states to avoid infinite loops
            # Key: (node_id, z_hops_taken, last_axis, y_direction_committed, has_gone_upstream, has_gone_to_parent)
            visited_states = set()
            visited_states.add((start_node['id'], 0, None, None, False, False))

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
                    z_direction,
                    current_state.z_hops_taken,
                    max_z_hops,
                    current_state.y_direction_committed,
                    current_state.has_gone_upstream,
                    current_state.has_gone_to_parent
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

                    # Determine Y-direction commitment
                    # Once we take a Y-axis step from base node, we commit to that direction
                    # This prevents traversing to sibling nodes
                    new_y_direction_committed = current_state.y_direction_committed
                    if edge_axis == Axis.Y and current_state.y_direction_committed is None:
                        # First Y-axis hop from base node - commit to this direction
                        new_y_direction_committed = neighbor_info.get('y_direction')

                    # Track if we've gone upstream (X-axis only)
                    # Z-axis should only be available from input node and its children (downstream)
                    # Once we go upstream, Z-axis is no longer available
                    new_has_gone_upstream = current_state.has_gone_upstream
                    if edge_axis == Axis.X and neighbor_info.get('x_direction') == 'upstream':
                        new_has_gone_upstream = True

                    # Track if we've gone "up" to a parent node (Y-axis only)
                    # Z-axis should only be available from input node and its descendants
                    # Once we go "up" to a parent, Z-axis is no longer available
                    new_has_gone_to_parent = current_state.has_gone_to_parent
                    if edge_axis == Axis.Y and neighbor_info.get('y_direction') == 'up':
                        new_has_gone_to_parent = True

                    # Create state key to avoid revisiting same state
                    state_key = (neighbor_id, new_z_hops, edge_axis, new_y_direction_committed, new_has_gone_upstream, new_has_gone_to_parent)

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
                        path_edges=new_path_edges,
                        y_direction_committed=new_y_direction_committed,
                        has_gone_upstream=new_has_gone_upstream,
                        has_gone_to_parent=new_has_gone_to_parent
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

    def one_hop(
        self,
        start_node_id: str,
        axes: List[str] = None,
        z_direction: str = "both"
    ) -> OneHopResult:
        """
        Get immediate neighbors (1-hop) from a node, grouped by axis and direction.

        This provides a "what's directly connected?" view following the same
        traversal rules as the full traverse method, but limited to 1 hop.

        Args:
            start_node_id: ID of the starting node
            axes: List of axes to include ['x', 'y', 'z'] or subset (default: all)
            z_direction: 'outgoing' (edges where node is source),
                         'incoming' (edges where node is target), or 'both'

        Returns:
            OneHopResult with neighbors grouped by axis and direction
        """
        if axes is None:
            axes = ['x', 'y', 'z']

        axes = [Axis(a) for a in axes]

        with self.driver.session() as session:
            # Get start node info
            start_node = self._get_node(session, start_node_id)
            if not start_node:
                raise ValueError(f"Start node {start_node_id} not found")

            # Initialize result containers
            x_upstream = []
            x_downstream = []
            y_up = []
            y_down = []
            z_outgoing = []  # Z-edges where start_node is the source
            z_incoming = []  # Z-edges where start_node is the target

            # Get all neighbors respecting axis constraints
            # Z-hops = 0 since we're at the base node, so Z-axis is available
            # Y-direction not committed yet since we're at base node
            # has_gone_upstream = False since we're at base node
            # has_gone_to_parent = False since we're at base node
            neighbors = self._get_neighbors(
                session,
                start_node['id'],
                start_node['type'],
                start_node.get('sub_type'),
                axes,
                x_direction="both",
                y_direction="both",
                z_direction=z_direction,
                current_z_hops=0,  # At base node, Z is available
                max_z_hops=1,
                y_direction_committed=None,  # At base node, no Y-direction committed yet
                has_gone_upstream=False,  # At base node, haven't gone upstream
                has_gone_to_parent=False  # At base node, haven't gone to parent
            )

            # Group neighbors by axis and direction
            for neighbor_info in neighbors:
                neighbor_node = neighbor_info['node']
                edge = neighbor_info['edge']
                edge_axis = neighbor_info['axis']
                classification = neighbor_info['classification']

                # Build neighbor result entry
                neighbor_entry = {
                    'node': neighbor_node,
                    'edge': edge,
                    'edge_type': edge['type'],
                    'axis': edge_axis.value
                }

                if edge_axis == Axis.X:
                    # Determine if this is upstream or downstream
                    is_outgoing = edge['source'] == start_node['id']
                    semantic_dir = classification.semantic_direction

                    if is_outgoing:
                        edge_semantic = semantic_dir
                    else:
                        edge_semantic = (
                            SemanticDirection.DOWNSTREAM
                            if semantic_dir == SemanticDirection.UPSTREAM
                            else SemanticDirection.UPSTREAM
                        )

                    if edge_semantic == SemanticDirection.UPSTREAM:
                        x_upstream.append(neighbor_entry)
                    else:
                        x_downstream.append(neighbor_entry)

                elif edge_axis == Axis.Y:
                    # Determine if this is up or down
                    is_outgoing = edge['source'] == start_node['id']
                    semantic_up = classification.semantic_up

                    if semantic_up == SemanticDirection.FORWARD:
                        actual_dir = "up" if is_outgoing else "down"
                    else:
                        actual_dir = "down" if is_outgoing else "up"

                    if actual_dir == "up":
                        y_up.append(neighbor_entry)
                    else:
                        y_down.append(neighbor_entry)

                elif edge_axis == Axis.Z:
                    # Bucket by whether start_node is the source (outgoing) or target (incoming)
                    is_outgoing = edge['source'] == start_node['id']
                    if is_outgoing:
                        z_outgoing.append(neighbor_entry)
                    else:
                        z_incoming.append(neighbor_entry)

            return OneHopResult(
                start_node=start_node,
                x_axis={
                    "upstream": x_upstream,
                    "downstream": x_downstream
                },
                y_axis={
                    "up": y_up,
                    "down": y_down
                },
                z_axis={
                    "outgoing": z_outgoing,
                    "incoming": z_incoming
                },
                metadata={
                    'total_x_upstream': len(x_upstream),
                    'total_x_downstream': len(x_downstream),
                    'total_y_up': len(y_up),
                    'total_y_down': len(y_down),
                    'total_z_outgoing': len(z_outgoing),
                    'total_z_incoming': len(z_incoming),
                    'total_z': len(z_outgoing) + len(z_incoming)
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
        z_direction: str,
        current_z_hops: int,
        max_z_hops: int,
        y_direction_committed: Optional[str] = None,
        has_gone_upstream: bool = False,
        has_gone_to_parent: bool = False
    ) -> List[Dict]:
        """
        Get all valid neighbors of a node based on traversal parameters.

        Returns list of dicts with keys: node, edge, axis, classification, y_direction (for Y-axis edges), x_direction (for X-axis edges)
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
            # Z-axis hops are only allowed from the input node and its children (descendants)
            # This means:
            # 1. Once we've made ANY Z-hop in the path, no more Z-hops are allowed
            # 2. Once we've gone upstream (X-axis) from the input node, no Z-hops are allowed
            # 3. Once we've gone "up" (Y-axis) to a parent node, no Z-hops are allowed
            # This ensures Z-hops only occur from the starting node or its descendants
            if classification.axis == Axis.Z:
                if current_z_hops > 0:
                    # Already taken a Z-hop, cannot continue on Z-axis
                    # After a Z-hop, only X and Y axis traversal is allowed
                    continue
                if has_gone_upstream:
                    # We've traversed upstream - Z-axis no longer available
                    # Parent node Z-axis relationships may not be relevant to chosen node
                    continue
                if has_gone_to_parent:
                    # We've traversed "up" to a parent node - Z-axis no longer available
                    # Parent node Z-axis relationships may not be relevant to chosen node
                    continue

            # Check direction constraints
            should_traverse = self._should_traverse_edge(
                classification,
                is_outgoing,
                x_direction,
                y_direction,
                z_direction
            )

            if not should_traverse:
                continue

            # For X-axis edges, determine actual direction (upstream/downstream)
            actual_x_direction = None
            if classification.axis == Axis.X:
                semantic_dir = classification.semantic_direction

                if is_outgoing:
                    edge_semantic = semantic_dir
                else:
                    edge_semantic = (
                        SemanticDirection.DOWNSTREAM
                        if semantic_dir == SemanticDirection.UPSTREAM
                        else SemanticDirection.UPSTREAM
                    )

                actual_x_direction = "upstream" if edge_semantic == SemanticDirection.UPSTREAM else "downstream"

            # For Y-axis edges, check direction commitment to prevent sibling traversal
            actual_y_direction = None
            if classification.axis == Axis.Y:
                # Determine actual direction being taken
                semantic_up = classification.semantic_up
                if semantic_up == SemanticDirection.FORWARD:
                    actual_y_direction = "up" if is_outgoing else "down"
                else:  # semantic_up == REVERSE
                    actual_y_direction = "down" if is_outgoing else "up"

                # If we've already committed to a Y direction, enforce it
                if y_direction_committed is not None:
                    if actual_y_direction != y_direction_committed:
                        # Trying to reverse Y direction - skip to prevent sibling traversal
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

            neighbor_info = {
                'node': neighbor_node,
                'edge': edge_dict,
                'axis': classification.axis,
                'classification': classification
            }

            # Include X direction for X-axis edges (used for upstream tracking)
            if actual_x_direction is not None:
                neighbor_info['x_direction'] = actual_x_direction

            # Include Y direction for Y-axis edges (used for direction commitment)
            if actual_y_direction is not None:
                neighbor_info['y_direction'] = actual_y_direction

            neighbors.append(neighbor_info)

        return neighbors

    def _should_traverse_edge(
        self,
        classification,
        is_outgoing: bool,
        x_direction: str,
        y_direction: str,
        z_direction: str = "both"
    ) -> bool:
        """
        Determine if an edge should be traversed based on direction constraints.

        Args:
            classification: EdgeClassification object
            is_outgoing: Whether we're traversing in the stored edge direction
            x_direction: 'upstream', 'downstream', or 'both'
            y_direction: 'up', 'down', or 'both'
            z_direction: 'outgoing' (node is source), 'incoming' (node is target), or 'both'

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
            # Z-axis: filter by edge direction relative to the current node.
            # 'outgoing' = current node is source (we follow the stored edge forward)
            # 'incoming' = current node is target (we follow the stored edge backward)
            # 'both'     = traverse in either direction (original behavior)
            if z_direction == "both":
                return True
            elif z_direction == "outgoing":
                return is_outgoing
            elif z_direction == "incoming":
                return not is_outgoing

        return False
