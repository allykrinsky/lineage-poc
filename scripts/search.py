#!/usr/bin/env python3
"""Perform hybrid search queries."""
import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.graph.embeddings import GraphEmbeddingManager
from src.search.query import HybridSearcher
from src.utils import Config


def main():
    """Run hybrid search queries."""
    parser = argparse.ArgumentParser(
        description="Hybrid search with BM25, semantic, and optional graph embeddings."
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="borrower capacity deterioration",
        help="Search query (default: 'borrower capacity deterioration')"
    )
    parser.add_argument(
        "--no-graph",
        action="store_true",
        help="Disable graph-based KNN search"
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of results to return (default: 10)"
    )
    args = parser.parse_args()

    use_graph = not args.no_graph
    print(f"Graph embeddings enabled: {use_graph}")

    # Initialize searcher
    print("\n🔌 Initializing searcher...")
    searcher = HybridSearcher(
        opensearch_url=Config.OPENSEARCH_URL,
        index_name=Config.OPENSEARCH_INDEX,
        model_name=Config.SENTENCE_TRANSFORMER_MODEL,
        bm25_weight=Config.BM25_WEIGHT,
        semantic_weight=Config.SEMANTIC_WEIGHT,
        graph_weight=Config.GRAPH_WEIGHT
    )

    # Load graph data if needed
    if use_graph:
        print("🔄 Loading nodes and embeddings from Neo4j...")
        embedding_manager = GraphEmbeddingManager(
            uri=Config.NEO4J_URI,
            user=Config.NEO4J_USER,
            password=Config.NEO4J_PASSWORD
        )

        try:
            full_nodes = embedding_manager.load_full_nodes()
            graph_embeddings = embedding_manager.load_node2vec_embeddings()
            searcher.load_graph_data(full_nodes, graph_embeddings)
        finally:
            embedding_manager.close()

    # Perform search
    print(f"\n🔍 Query: {args.query}")
    results = searcher.hybrid_search(args.query, top_n=args.top_n, use_graph=use_graph)

    # Display results
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    for result in results:
        print(f"\n{result['id']:10} | {result['entity_type']:10} | Score: {result['total_score']:.4f}")
        print(f"Title: {result['title']}")
        print(f"Reason: {result['reason']}")


if __name__ == "__main__":
    main()
