"""
Edge Taxonomy Configuration Loader

Loads and parses edge_taxonomy.yaml to classify edges by axis (X/Y/Z)
and provide traversal rules for the query engine.
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum


class Axis(str, Enum):
    """Graph traversal axes"""
    X = "x"  # Lineage / Derivation
    Y = "y"  # Hierarchy / Containment
    Z = "z"  # Association / Cross-cutting


class SemanticDirection(str, Enum):
    """Semantic direction for traversal"""
    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"
    UP = "up"
    DOWN = "down"
    FORWARD = "forward"
    REVERSE = "reverse"


@dataclass
class EdgeClassification:
    """Classification metadata for a single edge type"""
    edge_name: str
    source_type: str
    destination_type: str
    source_sub_type: Optional[List[str]]
    destination_sub_type: Optional[List[str]]
    axis: Axis
    semantic_direction: Optional[SemanticDirection]
    semantic_up: Optional[SemanticDirection]  # For Y-axis
    hop_group: Optional[str]
    hop_role: Optional[str]
    passthrough: bool
    reverse: bool
    description: str


@dataclass
class NodeTypeInfo:
    """Node type metadata"""
    name: str
    display_name: str
    role: str  # resource, transformer, structural, container, qualifier
    visible: bool
    sub_types: List[str]
    collapse_to: List[str]  # For passthrough nodes


@dataclass
class HopGroup:
    """Hop group definition for X-axis collapsing"""
    name: str
    description: str
    resource_types: List[str]
    transformer_type: str
    upstream_edge: str
    downstream_edge: str


class EdgeTaxonomy:
    """
    Loads and provides access to edge taxonomy configuration.

    This is the single source of truth for how edges are classified
    and traversed in the lineage graph.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize taxonomy from config file.

        Args:
            config_path: Path to edge_taxonomy.yaml. If None, uses default location.
        """
        if config_path is None:
            # Default to edge_taxonomy.yaml in project root
            config_path = Path(__file__).parent.parent.parent / "edge_taxonomy.yaml"

        self.config_path = config_path
        self.config = self._load_config()

        # Parse node types
        self.node_types: Dict[str, NodeTypeInfo] = self._parse_node_types()

        # Parse edge classifications
        self.x_edges: Dict[Tuple, EdgeClassification] = {}
        self.y_edges: Dict[Tuple, EdgeClassification] = {}
        self.z_edges: Dict[Tuple, EdgeClassification] = {}
        self._parse_edges()

        # Parse hop groups
        self.hop_groups: Dict[str, HopGroup] = self._parse_hop_groups()

        # Parse traversal rules
        self.traversal_rules = self.config.get('traversal_rules', {})

    def _load_config(self) -> dict:
        """Load YAML configuration file"""
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def _parse_node_types(self) -> Dict[str, NodeTypeInfo]:
        """Parse node type definitions"""
        node_types = {}
        for node_name, node_config in self.config.get('node_types', {}).items():
            node_types[node_name] = NodeTypeInfo(
                name=node_name,
                display_name=node_config.get('display_name', node_name),
                role=node_config.get('role', 'resource'),
                visible=node_config.get('visible', True),
                sub_types=node_config.get('sub_types', []),
                collapse_to=node_config.get('collapse_to', [])
            )
        return node_types

    def _normalize_sub_type(self, sub_type) -> Optional[List[str]]:
        """Normalize sub_type to a list"""
        if sub_type is None or sub_type == "null":
            return None
        if isinstance(sub_type, str):
            return [sub_type]
        return sub_type

    def _parse_edges(self):
        """Parse edge definitions from all three axes"""
        # X-axis (lineage)
        for edge_def in self.config.get('x_lineage', []):
            key = self._edge_key(
                edge_def['edge_name'],
                edge_def['source'],
                edge_def['destination'],
                edge_def.get('source_sub_type'),
                edge_def.get('destination_sub_type')
            )
            self.x_edges[key] = EdgeClassification(
                edge_name=edge_def['edge_name'],
                source_type=edge_def['source'],
                destination_type=edge_def['destination'],
                source_sub_type=self._normalize_sub_type(edge_def.get('source_sub_type')),
                destination_sub_type=self._normalize_sub_type(edge_def.get('destination_sub_type')),
                axis=Axis.X,
                semantic_direction=SemanticDirection(edge_def['semantic_direction']),
                semantic_up=None,
                hop_group=edge_def.get('hop_group'),
                hop_role=edge_def.get('hop_role'),
                passthrough=edge_def.get('passthrough', False),
                reverse=edge_def.get('reverse', False),
                description=edge_def.get('description', '')
            )

        # Y-axis (hierarchy)
        for edge_def in self.config.get('y_hierarchy', []):
            key = self._edge_key(
                edge_def['edge_name'],
                edge_def['source'],
                edge_def['destination'],
                edge_def.get('source_sub_type'),
                edge_def.get('destination_sub_type')
            )
            self.y_edges[key] = EdgeClassification(
                edge_name=edge_def['edge_name'],
                source_type=edge_def['source'],
                destination_type=edge_def['destination'],
                source_sub_type=self._normalize_sub_type(edge_def.get('source_sub_type')),
                destination_sub_type=self._normalize_sub_type(edge_def.get('destination_sub_type')),
                axis=Axis.Y,
                semantic_direction=None,
                semantic_up=SemanticDirection(edge_def['semantic_up']),
                hop_group=None,
                hop_role=None,
                passthrough=edge_def.get('passthrough', False),
                reverse=edge_def.get('reverse', False),
                description=edge_def.get('description', '')
            )

        # Z-axis (association)
        for edge_def in self.config.get('z_association', []):
            key = self._edge_key(
                edge_def['edge_name'],
                edge_def['source'],
                edge_def['destination'],
                edge_def.get('source_sub_type'),
                edge_def.get('destination_sub_type')
            )
            self.z_edges[key] = EdgeClassification(
                edge_name=edge_def['edge_name'],
                source_type=edge_def['source'],
                destination_type=edge_def['destination'],
                source_sub_type=self._normalize_sub_type(edge_def.get('source_sub_type')),
                destination_sub_type=self._normalize_sub_type(edge_def.get('destination_sub_type')),
                axis=Axis.Z,
                semantic_direction=None,
                semantic_up=None,
                hop_group=None,
                hop_role=None,
                passthrough=edge_def.get('passthrough', False),
                reverse=edge_def.get('reverse', False),
                description=edge_def.get('description', '')
            )

    def _edge_key(
        self,
        edge_name: str,
        source_type: str,
        dest_type: str,
        source_sub_type: Optional[List[str]],
        dest_sub_type: Optional[List[str]]
    ) -> Tuple:
        """
        Create a unique key for edge lookup.

        Key format: (edge_name_upper, source_type, dest_type, source_sub_type_tuple, dest_sub_type_tuple)
        """
        # Normalize edge name to uppercase for matching
        edge_name_norm = edge_name.upper()

        # Normalize sub_types to tuples for hashing
        source_sub_tuple = tuple(sorted(source_sub_type)) if source_sub_type else None
        dest_sub_tuple = tuple(sorted(dest_sub_type)) if dest_sub_type else None

        return (edge_name_norm, source_type, dest_type, source_sub_tuple, dest_sub_tuple)

    def _parse_hop_groups(self) -> Dict[str, HopGroup]:
        """Parse hop group definitions"""
        hop_groups = {}
        for group_name, group_def in self.config.get('hop_groups', {}).items():
            hop_groups[group_name] = HopGroup(
                name=group_name,
                description=group_def.get('description', ''),
                resource_types=group_def.get('resource_types', []),
                transformer_type=group_def.get('transformer_type', ''),
                upstream_edge=group_def.get('upstream_edge', ''),
                downstream_edge=group_def.get('downstream_edge', '')
            )
        return hop_groups

    def classify_edge(
        self,
        edge_type: str,
        source_node_type: str,
        dest_node_type: str,
        source_sub_type: Optional[str] = None,
        dest_sub_type: Optional[str] = None
    ) -> Optional[EdgeClassification]:
        """
        Classify an edge by looking it up in the taxonomy.

        Args:
            edge_type: The Neo4j relationship type (e.g., "DATASET_PRODUCED_BY")
            source_node_type: The source node's type
            dest_node_type: The destination node's type
            source_sub_type: Optional source node sub_type
            dest_sub_type: Optional destination node sub_type

        Returns:
            EdgeClassification if found, None otherwise
        """
        # Try exact match first (with sub_types)
        source_sub_list = [source_sub_type] if source_sub_type else None
        dest_sub_list = [dest_sub_type] if dest_sub_type else None

        key = self._edge_key(edge_type, source_node_type, dest_node_type, source_sub_list, dest_sub_list)

        # Try all three axes
        for edge_dict in [self.x_edges, self.y_edges, self.z_edges]:
            if key in edge_dict:
                return edge_dict[key]

        # Try without sub_types if not found
        key_no_sub = self._edge_key(edge_type, source_node_type, dest_node_type, None, None)
        for edge_dict in [self.x_edges, self.y_edges, self.z_edges]:
            if key_no_sub in edge_dict:
                return edge_dict[key_no_sub]

        # Try matching with any sub_type on destination
        if dest_sub_type:
            for edge_dict in [self.x_edges, self.y_edges, self.z_edges]:
                for stored_key, classification in edge_dict.items():
                    stored_edge, stored_src, stored_dst, stored_src_sub, stored_dst_sub = stored_key
                    if (stored_edge == edge_type.upper() and
                        stored_src == source_node_type and
                        stored_dst == dest_node_type):
                        # Check if dest_sub_type matches
                        if stored_dst_sub and dest_sub_type in stored_dst_sub:
                            return classification

        return None

    def get_max_z_hops(self) -> int:
        """Get the maximum allowed Z-axis hops from config"""
        return self.traversal_rules.get('z_axis', {}).get('max_hops', 1)

    def is_passthrough_node(self, node_type: str) -> bool:
        """Check if a node type is passthrough (should be collapsed)"""
        node_info = self.node_types.get(node_type)
        return node_info and not node_info.visible

    def get_node_role(self, node_type: str) -> str:
        """Get the role of a node type (resource, transformer, etc.)"""
        node_info = self.node_types.get(node_type)
        return node_info.role if node_info else 'resource'
