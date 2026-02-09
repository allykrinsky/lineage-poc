#!/usr/bin/env python3
"""Index entities with semantic and graph embeddings in OpenSearch."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.graph.embeddings import GraphEmbeddingManager
from src.search.indexer import SearchIndexer
from src.utils import Config


def main():
    """Load embeddings from Neo4j and index in OpenSearch."""
    print("🚀 Starting embedding indexing...")

    # Connect to Neo4j
    print("\n🔌 Connecting to Neo4j...")
    embedding_manager = GraphEmbeddingManager(
        uri=Config.NEO4J_URI,
        user=Config.NEO4J_USER,
        password=Config.NEO4J_PASSWORD
    )

    try:
        # Load data from Neo4j
        print("📥 Fetching Node2Vec graph embeddings...")
        graph_embeddings = embedding_manager.load_node2vec_embeddings()
        print(f"   Loaded {len(graph_embeddings)} graph embeddings")

        print("📥 Fetching nodes...")
        nodes = embedding_manager.load_nodes()
        print(f"   Loaded {len(nodes)} nodes")

    finally:
        embedding_manager.close()

    # Index in OpenSearch
    print("\n🔍 Indexing in OpenSearch...")
    indexer = SearchIndexer(
        opensearch_url=Config.OPENSEARCH_URL,
        index_name=Config.OPENSEARCH_INDEX,
        model_name=Config.SENTENCE_TRANSFORMER_MODEL
    )

    indexer.index_all(nodes, graph_embeddings)

    print("\n✨ Indexing complete!")
    print("   You can now run 'python scripts/search.py' to perform searches.")


if __name__ == "__main__":
    main()
