"""
Pytest configuration and fixtures for traversal engine tests.
"""

import pytest
from neo4j import GraphDatabase
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from src.utils import Config
from src.traversal.taxonomy import EdgeTaxonomy
from src.traversal.engine import TraversalEngine


@pytest.fixture(scope="session")
def neo4j_driver():
    """Create Neo4j driver for testing"""
    driver = GraphDatabase.driver(
        Config.NEO4J_URI,
        auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD)
    )
    yield driver
    driver.close()


@pytest.fixture(scope="session")
def taxonomy():
    """Load edge taxonomy configuration"""
    taxonomy_path = Path(__file__).parent.parent / "metamodel" / "edge_taxonomy.yaml"
    return EdgeTaxonomy(taxonomy_path)


@pytest.fixture(scope="function")
def traversal_engine(taxonomy):
    """Create traversal engine for each test"""
    engine = TraversalEngine(
        Config.NEO4J_URI,
        Config.NEO4J_USER,
        Config.NEO4J_PASSWORD,
        taxonomy
    )
    yield engine
    engine.close()


@pytest.fixture(scope="session")
def verify_graph_loaded(neo4j_driver):
    """Verify that the graph has been loaded with seed data"""
    with neo4j_driver.session() as session:
        result = session.run("MATCH (n) RETURN count(n) as count")
        count = result.single()['count']

        if count == 0:
            pytest.fail(
                "Neo4j database is empty. Please run the seed script first:\n"
                "  docker-compose up -d\n"
                "  python -c 'from neo4j import GraphDatabase; "
                "driver = GraphDatabase.driver(\"bolt://localhost:7687\", auth=(\"neo4j\", \"password\")); "
                "with driver.session() as session: "
                "session.run(open(\"seed_graph.cypher\").read())'"
            )

    return True
