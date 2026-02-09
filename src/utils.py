"""Shared utility functions."""
import os
from pathlib import Path


def get_project_root() -> Path:
    """
    Get the project root directory.

    Returns:
        Path to project root
    """
    return Path(__file__).parent.parent


def get_config_path(filename: str = None) -> Path:
    """
    Get path to config directory or file.

    Args:
        filename: Optional config filename

    Returns:
        Path to config directory or specific config file
    """
    config_dir = get_project_root()
    if filename:
        return config_dir / filename
    return config_dir


def get_metamodel_path(filename: str = None) -> Path:
    """
    Get path to metamodel config directory or file.

    Args:
        filename: Optional metamodel filename

    Returns:
        Path to metamodel directory or specific metamodel file
    """
    metamodel_dir = get_config_path("metamodel")
    if filename:
        return metamodel_dir / filename
    return metamodel_dir


class Config:
    """Configuration constants."""

    # Neo4j
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

    # OpenSearch
    OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
    OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "entities")

    # Models
    SENTENCE_TRANSFORMER_MODEL = os.getenv(
        "SENTENCE_TRANSFORMER_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2"
    )

    # Search weights
    BM25_WEIGHT = float(os.getenv("BM25_WEIGHT", "1.5"))
    SEMANTIC_WEIGHT = float(os.getenv("SEMANTIC_WEIGHT", "2.0"))
    GRAPH_WEIGHT = float(os.getenv("GRAPH_WEIGHT", "1.5"))
