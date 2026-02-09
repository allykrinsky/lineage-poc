"""Graph embedding utilities."""
import numpy as np
from typing import Dict
from neo4j import GraphDatabase


class GraphEmbeddingManager:
    """Manages graph embeddings from Neo4j."""

    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize the embedding manager.

        Args:
            uri: Neo4j connection URI
            user: Neo4j username
            password: Neo4j password
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        """Close the Neo4j driver connection."""
        self.driver.close()

    def load_node2vec_embeddings(self) -> Dict[str, np.ndarray]:
        """
        Load Node2Vec embeddings from Neo4j.

        Returns:
            Dictionary mapping node IDs to embedding vectors
        """
        query = """
        MATCH (n)
        RETURN n.id AS id, n.n2v AS embedding
        """
        embeddings = {}
        with self.driver.session() as session:
            for row in session.run(query):
                emb = row["embedding"]
                if emb is not None:
                    embeddings[row["id"]] = np.array(emb, dtype=float)
        return embeddings

    def load_fastrp_embeddings(self, projection_name: str = "domainGraph") -> Dict[str, list]:
        """
        Load FastRP embeddings from Neo4j GDS.

        Args:
            projection_name: Name of the GDS graph projection

        Returns:
            Dictionary mapping node IDs to embedding vectors
        """
        query = f"""
        CALL gds.fastRP.stream('{projection_name}', {{embeddingDimension: 64}})
        YIELD nodeId, embedding
        RETURN gds.util.asNode(nodeId).id AS id, embedding
        """
        embeddings = {}
        with self.driver.session() as session:
            for row in session.run(query):
                embeddings[row["id"]] = row["embedding"]
        return embeddings

    def load_nodes(self) -> list:
        """
        Load all nodes with their properties.

        Returns:
            List of node records with id, properties, and type
        """
        query = """
        MATCH (n)
        RETURN n.id AS id, n AS props, labels(n)[0] AS type
        """
        with self.driver.session() as session:
            return list(session.run(query))

    def load_full_nodes(self) -> Dict[str, Dict]:
        """
        Load all nodes with complete metadata.

        Returns:
            Dictionary mapping node IDs to node data
        """
        query = """
        MATCH (n)
        RETURN n.id AS id, labels(n) AS labels, n AS props
        """
        nodes = {}
        with self.driver.session() as session:
            for row in session.run(query):
                node_id = row["id"]
                data = dict(row["props"])
                data["labels"] = row["labels"]
                data["id"] = node_id
                nodes[node_id] = data
        return nodes
