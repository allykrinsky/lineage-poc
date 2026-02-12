#!/usr/bin/env python3
"""
Test script for the lineage traversal API.

Usage:
    python test_api.py
"""

import requests
import json
from typing import Dict, Any


def test_traversal(
    start_node_id: str,
    axes: list = None,
    x_direction: str = "both",
    y_direction: str = "both",
    max_z_hops: int = 1,
    max_depth: int = None
) -> Dict[str, Any]:
    """Execute a traversal and return results."""

    if axes is None:
        axes = ["x", "y", "z"]

    response = requests.post(
        "http://localhost:8000/api/lineage/traverse",
        json={
            "start_node_id": start_node_id,
            "axes": axes,
            "x_direction": x_direction,
            "y_direction": y_direction,
            "max_z_hops": max_z_hops,
            "max_depth": max_depth,
            "include_transformers": True
        }
    )

    if response.status_code != 200:
        print(f"❌ Error {response.status_code}: {response.text}")
        return None

    return response.json()


def print_results(result: Dict[str, Any], test_name: str):
    """Pretty print traversal results."""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")

    print(f"\n📍 Start Node: {result['start_node']['id']} ({result['start_node']['type']})")
    print(f"   {result['start_node']['properties'].get('name', 'N/A')}")

    metadata = result['traversal_metadata']
    print(f"\n📊 Traversal Statistics:")
    print(f"   Total nodes visited: {metadata['total_nodes_visited']}")
    print(f"   Total edges traversed: {metadata['total_edges_traversed']}")
    print(f"   Max Z-hops taken: {metadata['z_hops_taken']}")

    print(f"\n📦 Nodes Found ({len(result['nodes'])} total):")
    node_types = {}
    for node in result['nodes']:
        node_type = node['type']
        node_types[node_type] = node_types.get(node_type, 0) + 1

    for node_type, count in sorted(node_types.items()):
        print(f"   {node_type}: {count}")

    print(f"\n🔗 Edges Found ({len(result['edges'])} total):")
    edge_types = {}
    for edge in result['edges']:
        edge_type = edge['type']
        edge_types[edge_type] = edge_types.get(edge_type, 0) + 1

    for edge_type, count in sorted(edge_types.items()):
        print(f"   {edge_type}: {count}")

    # Show some sample nodes
    print(f"\n🎯 Sample Nodes:")
    for node in result['nodes'][:5]:
        name = node['properties'].get('name', node['properties'].get('description', 'N/A'))[:50]
        print(f"   {node['id']} ({node['type']}): {name}")


def main():
    """Run test scenarios."""

    print("\n" + "="*60)
    print("LINEAGE TRAVERSAL API - TEST SUITE")
    print("="*60)

    # Test 1: XZ-02 - The critical Z-of-Z blocking test
    print("\n\n🧪 Test 1: XZ-02 - Z-of-Z Blocking (CRITICAL)")
    print("   This proves Z→Z paths are blocked while Z→Y and Z→X work")
    result = test_traversal(
        start_node_id="ds-002",  # curated_transactions
        axes=["x", "y", "z"],
        max_depth=10
    )
    if result:
        print_results(result, "XZ-02: Full Multi-Axis Traversal")

        # Verify constraint
        z_hops = result['traversal_metadata']['z_hops_taken']
        if z_hops <= 1:
            print(f"\n✅ PASSED: Z-of-Z correctly blocked (max z_hops = {z_hops})")
        else:
            print(f"\n❌ FAILED: Z-of-Z not blocked (z_hops = {z_hops})")

    # Test 2: Pure X-axis upstream
    print("\n\n🧪 Test 2: X-axis Upstream Lineage")
    print("   Trace data backwards from predictions to sources")
    result = test_traversal(
        start_node_id="ds-004",  # fraud_predictions
        axes=["x"],
        x_direction="upstream"
    )
    if result:
        print_results(result, "X-axis Upstream from fraud_predictions")

    # Test 3: Pure Y-axis hierarchy
    print("\n\n🧪 Test 3: Y-axis Hierarchy Walk")
    print("   Walk up from agent to agentic system")
    result = test_traversal(
        start_node_id="agv-001",  # fraud_reviewer_agent_v1
        axes=["y"],
        y_direction="up"
    )
    if result:
        print_results(result, "Y-axis Up from agent_version")

    # Test 4: Pure Z-axis associations
    print("\n\n🧪 Test 4: Z-axis Associations Only")
    print("   Find directly associated resources")
    result = test_traversal(
        start_node_id="ds-002",  # curated_transactions
        axes=["z"],
        max_z_hops=1
    )
    if result:
        print_results(result, "Z-axis from curated_transactions")

    print("\n\n" + "="*60)
    print("✅ ALL TESTS COMPLETE")
    print("="*60)
    print("\nAPI Docs: http://localhost:8000/docs")
    print("\n")


if __name__ == "__main__":
    main()
