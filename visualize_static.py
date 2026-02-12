#!/usr/bin/env python3
"""
Generate a static visualization of traversal results.

Usage:
    pip install networkx matplotlib
    python visualize_static.py
"""

import requests
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import json


def fetch_traversal(start_node_id="ds-002", axes=None, max_depth=10):
    """Fetch traversal results from API."""
    if axes is None:
        axes = ["x", "y", "z"]

    response = requests.post(
        "http://localhost:8000/api/lineage/traverse",
        json={
            "start_node_id": start_node_id,
            "axes": axes,
            "x_direction": "both",
            "y_direction": "both",
            "max_z_hops": 1,
            "max_depth": max_depth,
            "include_transformers": True
        }
    )

    if response.status_code != 200:
        raise Exception(f"API error: {response.text}")

    return response.json()


def create_graph(data):
    """Create NetworkX graph from traversal data."""
    G = nx.DiGraph()

    # Add nodes
    for node in data['nodes']:
        G.add_node(
            node['id'],
            type=node['type'],
            label=node['properties'].get('name', node['id']),
            **node['properties']
        )

    # Add edges
    for edge in data['edges']:
        G.add_edge(
            edge['source'],
            edge['target'],
            type=edge['type']
        )

    return G


def get_node_color(node_type):
    """Get color for node type."""
    colors = {
        'dataset': '#4CAF50',
        'etl_job': '#FF9800',
        'model': '#2196F3',
        'model_version': '#03A9F4',
        'agent_version': '#9C27B0',
        'agentic_system': '#673AB7',
        'agentic_system_version': '#7E57C2',
        'workspace': '#FFC107',
        'workspace_service': '#FFB300',
        'use_case': '#E91E63',
        'attribute': '#8BC34A',
        'data_dependency': '#FF5722',
        'mcp_server': '#00BCD4',
        'mcp_tool': '#00ACC1',
        'mcp_resource': '#0097A7',
        'application': '#795548',
        'glossary': '#607D8B',
        'data_concept': '#9E9E9E'
    }
    return colors.get(node_type, '#999999')


def visualize_graph(data, output_file='traversal_graph.png'):
    """Create and save visualization."""
    G = create_graph(data)

    # Create figure
    fig, ax = plt.subplots(1, 1, figsize=(20, 16))
    fig.suptitle(
        f'Lineage Traversal from {data["start_node"]["id"]} '
        f'({data["traversal_metadata"]["total_nodes_visited"]} nodes, '
        f'max Z-hops: {data["traversal_metadata"]["z_hops_taken"]})',
        fontsize=16,
        fontweight='bold'
    )

    # Layout
    try:
        pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
    except:
        pos = nx.shell_layout(G)

    # Node colors by type
    node_colors = [get_node_color(G.nodes[node]['type']) for node in G.nodes()]

    # Node sizes (make start node bigger)
    node_sizes = [
        1500 if node == data['start_node']['id'] else 800
        for node in G.nodes()
    ]

    # Draw nodes
    nx.draw_networkx_nodes(
        G, pos,
        node_color=node_colors,
        node_size=node_sizes,
        alpha=0.9,
        edgecolors='black',
        linewidths=2,
        ax=ax
    )

    # Draw edges
    nx.draw_networkx_edges(
        G, pos,
        edge_color='gray',
        arrows=True,
        arrowsize=15,
        arrowstyle='->',
        width=2,
        alpha=0.6,
        connectionstyle='arc3,rad=0.1',
        ax=ax
    )

    # Labels
    labels = {node: G.nodes[node]['label'][:20] for node in G.nodes()}
    nx.draw_networkx_labels(
        G, pos,
        labels,
        font_size=8,
        font_weight='bold',
        font_color='white',
        ax=ax
    )

    # Edge labels
    edge_labels = {
        (edge[0], edge[1]): edge[2]['type']
        for edge in G.edges(data=True)
    }
    nx.draw_networkx_edge_labels(
        G, pos,
        edge_labels,
        font_size=6,
        font_color='red',
        ax=ax
    )

    # Legend
    node_types = {}
    for node in data['nodes']:
        node_type = node['type']
        node_types[node_type] = node_types.get(node_type, 0) + 1

    legend_text = '\n'.join([
        f'{type_name}: {count}'
        for type_name, count in sorted(node_types.items())
    ])

    ax.text(
        0.02, 0.98, legend_text,
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment='top',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8)
    )

    # Stats box
    stats_text = (
        f'Total Nodes: {data["traversal_metadata"]["total_nodes_visited"]}\n'
        f'Total Edges: {data["traversal_metadata"]["total_edges_traversed"]}\n'
        f'Max Z-Hops: {data["traversal_metadata"]["z_hops_taken"]}\n'
        f'Start Node: {data["start_node"]["id"]}'
    )

    ax.text(
        0.98, 0.98, stats_text,
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment='top',
        horizontalalignment='right',
        bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8)
    )

    ax.axis('off')
    plt.tight_layout()

    # Save
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n✅ Visualization saved to: {output_file}")
    print(f"   Open it to see the graph!\n")

    # Also try to open it
    try:
        import subprocess
        subprocess.run(['open', output_file], check=False)
    except:
        pass


def main():
    """Main entry point."""
    print("🎨 Fetching traversal data...")

    # Fetch data
    data = fetch_traversal(start_node_id="ds-002", axes=["x", "y", "z"])

    print(f"✅ Got {data['traversal_metadata']['total_nodes_visited']} nodes")
    print(f"   Max Z-hops: {data['traversal_metadata']['z_hops_taken']}")

    # Visualize
    print("\n🖼️  Creating visualization...")
    visualize_graph(data)

    print("Done! Check the PNG file.")


if __name__ == "__main__":
    main()
