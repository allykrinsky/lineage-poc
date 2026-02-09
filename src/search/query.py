"""Hybrid search implementation with BM25, semantic, and graph embeddings."""
import requests
import numpy as np
from typing import Dict, List, Tuple, Optional
from sentence_transformers import SentenceTransformer


class HybridSearcher:
    """Hybrid search combining BM25, semantic similarity, and graph embeddings."""

    def __init__(
        self,
        opensearch_url: str = "http://localhost:9200",
        index_name: str = "entities",
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        bm25_weight: float = 1.5,
        semantic_weight: float = 2.0,
        graph_weight: float = 1.5,
        rrf_k: int = 60,
        top_k_per_channel: int = 25
    ):
        """
        Initialize the hybrid searcher.

        Args:
            opensearch_url: OpenSearch base URL
            index_name: Index name to search
            model_name: Sentence transformer model name
            bm25_weight: Weight for BM25 results
            semantic_weight: Weight for semantic search results
            graph_weight: Weight for graph embedding results
            rrf_k: RRF constant for ranking fusion
            top_k_per_channel: Number of results to fetch per channel
        """
        self.search_url = f"{opensearch_url}/{index_name}/_search"
        self.bm25_weight = bm25_weight
        self.semantic_weight = semantic_weight
        self.graph_weight = graph_weight
        self.rrf_k = rrf_k
        self.top_k_per_channel = top_k_per_channel

        self.semantic_model = SentenceTransformer(model_name)
        self.node_embeddings: Dict[str, np.ndarray] = {}
        self.full_nodes: Dict[str, Dict] = {}

    def embed_semantic(self, node) -> np.ndarray:
        """
        Generate semantic embedding from text or node metadata.

        Args:
            node: String query or node dictionary

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

    def load_graph_data(self, full_nodes: Dict[str, Dict], graph_embeddings: Dict[str, np.ndarray]):
        """
        Load node metadata and graph embeddings for graph-based search.

        Args:
            full_nodes: Dictionary of node IDs to node data
            graph_embeddings: Dictionary of node IDs to graph embedding vectors
        """
        self.full_nodes = full_nodes
        self.graph_embeddings = graph_embeddings

        # Precompute normalized semantic embeddings for all nodes
        self.node_embeddings = {}
        for node_id, node in full_nodes.items():
            vec = self.embed_semantic(node)
            self.node_embeddings[node_id] = vec / (np.linalg.norm(vec) + 1e-9)

        print(f"✅ Loaded {len(full_nodes)} nodes for graph-based search.")

    def graph_query_embedding(self, query_text: str, top_k: int = 5) -> Tuple[List[float], List[str]]:
        """
        Build graph query embedding by averaging Node2Vec vectors of semantically similar anchor nodes.

        Args:
            query_text: Search query
            top_k: Number of anchor nodes to use

        Returns:
            Tuple of (graph query vector, list of anchor node IDs)
        """
        # Find semantically similar anchor nodes
        query_vec = self.embed_semantic(query_text)
        query_vec = query_vec / (np.linalg.norm(query_vec) + 1e-9)

        similarities = []
        for node_id, sem_vec in self.node_embeddings.items():
            sim = float(np.dot(query_vec, sem_vec))
            similarities.append((sim, node_id))

        similarities.sort(reverse=True)
        anchor_nodes = [node_id for sim, node_id in similarities[:top_k]]

        # Average their graph embeddings
        vectors = np.array([
            self.graph_embeddings[n]
            for n in anchor_nodes
            if n in self.graph_embeddings
        ])
        graph_query = vectors.mean(axis=0)

        print("\n🔍 DEBUG: Graph query anchors and vector")
        print("  Anchors:", anchor_nodes)
        print("  Graph query vector (first 10):", graph_query[:10])
        print("  Norm:", np.linalg.norm(graph_query))

        return graph_query.tolist(), anchor_nodes

    def search_bm25(self, query_text: str) -> List[Dict]:
        """
        Perform BM25 text search.

        Args:
            query_text: Search query

        Returns:
            List of search hits
        """
        payload = {
            "size": self.top_k_per_channel,
            "query": {
                "multi_match": {
                    "query": query_text,
                    "fields": ["title^3", "name^2", "description"]
                }
            }
        }
        response = requests.post(self.search_url, json=payload)
        response.raise_for_status()
        return response.json()["hits"]["hits"]

    def search_semantic(self, semantic_vec: np.ndarray) -> List[Dict]:
        """
        Perform semantic KNN search.

        Args:
            semantic_vec: Query semantic embedding

        Returns:
            List of search hits
        """
        payload = {
            "size": self.top_k_per_channel,
            "query": {
                "knn": {
                    "semantic_vector": {
                        "vector": semantic_vec.tolist(),
                        "k": self.top_k_per_channel
                    }
                }
            }
        }
        response = requests.post(self.search_url, json=payload)
        response.raise_for_status()
        return response.json()["hits"]["hits"]

    def search_graph(self, graph_vec: List[float]) -> List[Dict]:
        """
        Perform graph embedding KNN search.

        Args:
            graph_vec: Query graph embedding

        Returns:
            List of search hits
        """
        payload = {
            "size": self.top_k_per_channel,
            "query": {
                "knn": {
                    "graph_vector": {
                        "vector": graph_vec,
                        "k": self.top_k_per_channel
                    }
                }
            }
        }
        response = requests.post(self.search_url, json=payload)
        response.raise_for_status()
        return response.json()["hits"]["hits"]

    def rrf_score(self, rank: int) -> float:
        """
        Calculate Reciprocal Rank Fusion score.

        Args:
            rank: Result rank (1-indexed)

        Returns:
            RRF score
        """
        return 1.0 / (self.rrf_k + rank)

    def hybrid_search(
        self,
        query_text: str,
        top_n: int = 10,
        use_graph: bool = True
    ) -> List[Dict]:
        """
        Perform hybrid search with result explanations.

        Args:
            query_text: Search query
            top_n: Number of final results to return
            use_graph: Whether to include graph-based search

        Returns:
            List of ranked results with explanations
        """
        # Generate semantic embedding
        query_semantic = self.embed_semantic(query_text)

        # Perform searches
        bm25_hits = self.search_bm25(query_text)
        semantic_hits = self.search_semantic(query_semantic)

        if use_graph and self.graph_embeddings:
            graph_vec, anchor_nodes = self.graph_query_embedding(query_text)
            graph_hits = self.search_graph(graph_vec)
            print("\n🔍 DEBUG: Raw graph hits")
            for hit in graph_hits[:5]:
                print(f"  {hit['_id']} score={hit['_score']}")
        else:
            graph_hits = []
            anchor_nodes = []

        # Fusion scoring
        fused = {}

        def incorporate(hits: List[Dict], channel: str, weight: float):
            for rank, hit in enumerate(hits, 1):
                doc_id = hit["_id"]
                source = hit["_source"]

                channel_rrf = self.rrf_score(rank) * weight

                if doc_id not in fused:
                    fused[doc_id] = {
                        "title": source.get("title") or source.get("name"),
                        "entity_type": source.get("entity_type"),
                        "total_score": 0.0,
                        "channels": {}
                    }

                fused[doc_id]["channels"][channel] = {
                    "rank": rank,
                    "raw": hit["_score"],
                    "rrf": channel_rrf
                }

                fused[doc_id]["total_score"] += channel_rrf

        incorporate(bm25_hits, "bm25", self.bm25_weight)
        incorporate(semantic_hits, "semantic", self.semantic_weight)

        if use_graph and graph_hits:
            incorporate(graph_hits, "graph", self.graph_weight)

        # Sort and format results
        final = sorted(fused.items(), key=lambda x: x[1]["total_score"], reverse=True)[:top_n]

        results = []
        for doc_id, info in final:
            reasons = []

            if "bm25" in info["channels"]:
                reasons.append(f"text match (rank {info['channels']['bm25']['rank']})")

            if "semantic" in info["channels"]:
                reasons.append(f"semantic similarity (rank {info['channels']['semantic']['rank']})")

            if use_graph and "graph" in info["channels"]:
                labels = [
                    self.full_nodes[n]["title"] if self.full_nodes[n].get("title") else n
                    for n in anchor_nodes
                ]
                reasons.append("graph-close to: " + ", ".join(labels))

            results.append({
                "id": doc_id,
                "title": info["title"],
                "entity_type": info["entity_type"],
                "total_score": info["total_score"],
                "reason": "; ".join(reasons)
            })

        return results
