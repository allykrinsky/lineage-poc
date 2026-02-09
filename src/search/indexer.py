"""OpenSearch indexing operations."""
import requests
import numpy as np
from typing import Dict, Any, List
from sentence_transformers import SentenceTransformer


class SearchIndexer:
    """Handles OpenSearch indexing with semantic and graph embeddings."""

    def __init__(
        self,
        opensearch_url: str = "http://localhost:9200",
        index_name: str = "entities",
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    ):
        """
        Initialize the search indexer.

        Args:
            opensearch_url: OpenSearch base URL
            index_name: Name of the index to create/update
            model_name: Sentence transformer model name
        """
        self.opensearch_url = opensearch_url
        self.index_url = f"{opensearch_url}/{index_name}"
        self.index_name = index_name

        print(f"Loading SentenceTransformer model: {model_name}...")
        self.semantic_model = SentenceTransformer(model_name)

    def embed_semantic(self, node: Any) -> np.ndarray:
        """
        Build semantic embedding from node metadata.

        Args:
            node: Node data (string, dict, or None)

        Returns:
            Semantic embedding vector
        """
        if isinstance(node, str):
            return self.semantic_model.encode(node, convert_to_numpy=True)

        if node is None:
            return self.semantic_model.encode("empty node", convert_to_numpy=True)

        parts = []

        title = node.get("title") or node.get("name")
        if title:
            parts.append(str(title))

        desc = node.get("description")
        if desc:
            parts.append(str(desc))

        tags = node.get("tags")
        if isinstance(tags, list):
            parts.append(" ".join(tags))

        if not parts:
            parts.append(node.get("id", "unknown node"))

        text = " ".join(parts)
        return self.semantic_model.encode(text, convert_to_numpy=True)

    def create_index(self):
        """Create OpenSearch index with KNN vector fields."""
        mapping = {
            "settings": {"index.knn": True},
            "mappings": {
                "properties": {
                    "title": {"type": "text"},
                    "entity_type": {"type": "keyword"},
                    "semantic_vector": {
                        "type": "knn_vector",
                        "dimension": 384
                    },
                    "graph_vector": {
                        "type": "knn_vector",
                        "dimension": 64
                    }
                }
            }
        }

        print("Creating OpenSearch index...")
        requests.delete(self.index_url)
        response = requests.put(self.index_url, json=mapping)

        if response.status_code >= 300:
            print(f"Index creation warning: {response.text}")

    def index_documents(self, nodes: List[Dict], graph_embeddings: Dict[str, np.ndarray]):
        """
        Index documents with both semantic and graph embeddings.

        Args:
            nodes: List of node records from Neo4j
            graph_embeddings: Dictionary of node IDs to graph embedding vectors
        """
        for row in nodes:
            node_id = row["id"]
            props = dict(row["props"])
            entity_type = row["type"]

            # Generate semantic embedding
            semantic_vec = self.embed_semantic(props).tolist()

            # Get graph embedding
            if node_id in graph_embeddings:
                graph_vec = graph_embeddings[node_id].tolist()
            else:
                # Fallback to zero vector
                graph_vec = [0.0] * 64

            doc = {
                "title": props.get("title") or props.get("name"),
                "entity_type": entity_type,
                "semantic_vector": semantic_vec,
                "graph_vector": graph_vec
            }

            response = requests.put(f"{self.index_url}/_doc/{node_id}", json=doc)

            if response.status_code >= 300:
                print(f"INDEX ERROR for {node_id}: {response.text}")

        print("✅ Indexing complete.")

    def index_all(self, nodes: List[Dict], graph_embeddings: Dict[str, np.ndarray]):
        """
        Complete indexing pipeline.

        Args:
            nodes: List of node records from Neo4j
            graph_embeddings: Dictionary of node IDs to graph embedding vectors
        """
        self.create_index()
        self.index_documents(nodes, graph_embeddings)
        print("🎉 All embeddings loaded into OpenSearch.")
