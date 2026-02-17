"""
Lineage traversal engine package.

This package provides:
- Edge taxonomy classification
- Multi-axis graph traversal with constraints
- Hop collapsing for resource-transformer-resource patterns
"""

from .taxonomy import EdgeTaxonomy
from .engine import TraversalEngine

__all__ = ['EdgeTaxonomy', 'TraversalEngine']
