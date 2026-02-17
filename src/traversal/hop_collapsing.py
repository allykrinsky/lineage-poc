"""
Hop Collapsing Logic

Groups X-axis resource→transformer→resource pairs into single logical lineage steps.
"""

from typing import List, Dict, Optional
from .taxonomy import EdgeTaxonomy, Axis


class HopCollapser:
    """
    Collapses X-axis resource-transformer-resource patterns into logical hops.

    For example, Dataset → ETL Job → Dataset becomes a single logical step
    showing the source dataset, destination dataset, and transformation metadata.
    """

    def __init__(self, taxonomy: EdgeTaxonomy):
        """
        Initialize hop collapser.

        Args:
            taxonomy: Loaded edge taxonomy configuration
        """
        self.taxonomy = taxonomy

    def collapse_paths(self, paths: List[Dict], nodes: List[Dict]) -> List[Dict]:
        """
        Collapse resource-transformer-resource patterns in paths.

        Args:
            paths: List of path dictionaries from TraversalResult
            nodes: List of all nodes from TraversalResult

        Returns:
            List of collapsed paths with logical steps
        """
        node_lookup = {node['id']: node for node in nodes}
        collapsed_paths = []

        for path_info in paths:
            path_nodes = path_info['path']
            path_edges = path_info['edges']

            # Only collapse X-axis paths
            if path_info['axis'] != 'x':
                collapsed_paths.append(path_info)
                continue

            # Build logical steps
            logical_steps = self._build_logical_steps(
                path_nodes,
                path_edges,
                node_lookup
            )

            collapsed_path = {
                'axis': path_info['axis'],
                'z_hops': path_info['z_hops'],
                'logical_steps': logical_steps,
                'original_path': path_nodes,
                'original_edges': path_edges
            }

            collapsed_paths.append(collapsed_path)

        return collapsed_paths

    def _build_logical_steps(
        self,
        path_nodes: List[str],
        path_edges: List[Dict],
        node_lookup: Dict[str, Dict]
    ) -> List[Dict]:
        """
        Build logical steps from a path.

        Looks for resource→transformer→resource patterns and collapses them.
        """
        if len(path_nodes) < 2:
            return []

        logical_steps = []
        i = 0

        while i < len(path_edges):
            edge_info = path_edges[i]
            edge = edge_info['edge']
            classification = edge_info['classification']

            source_node_id = edge['source']
            target_node_id = edge['target']

            source_node = node_lookup.get(source_node_id)
            target_node = node_lookup.get(target_node_id)

            if not source_node or not target_node:
                i += 1
                continue

            source_role = self.taxonomy.get_node_role(source_node['type'])
            target_role = self.taxonomy.get_node_role(target_node['type'])

            # Check if this is part of a resource→transformer→resource pattern
            if self._is_hop_pattern(source_role, target_role, classification, path_edges, i):
                # Try to find the completing edge
                completing_edge = self._find_completing_edge(
                    target_node_id,
                    classification,
                    path_edges,
                    i + 1,
                    node_lookup
                )

                if completing_edge:
                    # Found a complete hop, collapse it
                    step = {
                        'from': source_node,
                        'to': completing_edge['dest_node'],
                        'via': target_node,
                        'hop_group': classification.hop_group,
                        'edge_names': [edge['type'], completing_edge['edge']['type']]
                    }
                    logical_steps.append(step)
                    i += 2  # Skip both edges
                else:
                    # Incomplete pattern, record as-is
                    step = {
                        'from': source_node,
                        'to': target_node,
                        'via': None,
                        'hop_group': classification.hop_group,
                        'edge_names': [edge['type']]
                    }
                    logical_steps.append(step)
                    i += 1
            else:
                # Not a hop pattern, record as simple step
                step = {
                    'from': source_node,
                    'to': target_node,
                    'via': None,
                    'hop_group': classification.hop_group,
                    'edge_names': [edge['type']]
                }
                logical_steps.append(step)
                i += 1

        return logical_steps

    def _is_hop_pattern(
        self,
        source_role: str,
        target_role: str,
        classification,
        path_edges: List[Dict],
        current_index: int
    ) -> bool:
        """
        Check if current edge is part of a resource→transformer pattern.

        Returns True if:
        - Source is resource and target is transformer, OR
        - Source is transformer and target is resource (reverse hop)
        """
        if not classification.hop_group:
            return False

        # Resource → Transformer
        if source_role == 'resource' and target_role == 'transformer':
            return True

        # Transformer → Resource
        if source_role == 'transformer' and target_role == 'resource':
            return True

        return False

    def _find_completing_edge(
        self,
        transformer_node_id: str,
        first_edge_classification,
        path_edges: List[Dict],
        start_index: int,
        node_lookup: Dict[str, Dict]
    ) -> Optional[Dict]:
        """
        Find the edge that completes a hop pattern.

        Given a resource→transformer edge, find the transformer→resource edge.
        They must share the same hop_group.
        """
        if start_index >= len(path_edges):
            return None

        # Look at the next edge
        next_edge_info = path_edges[start_index]
        next_edge = next_edge_info['edge']
        next_classification = next_edge_info['classification']

        # Check if it continues from the transformer
        if next_edge['source'] != transformer_node_id:
            return None

        # Check if it's in the same hop group
        if next_classification.hop_group != first_edge_classification.hop_group:
            return None

        # Get the destination node
        dest_node = node_lookup.get(next_edge['target'])
        if not dest_node:
            return None

        dest_role = self.taxonomy.get_node_role(dest_node['type'])

        # Check if destination is a resource
        if dest_role != 'resource':
            return None

        return {
            'edge': next_edge,
            'dest_node': dest_node,
            'classification': next_classification
        }
