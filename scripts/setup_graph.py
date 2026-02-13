#!/usr/bin/env python3
"""Setup and load the Neo4j graph from metamodel configuration."""
import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.metamodel.loader import MetamodelLoader
from src.graph.loader import GraphLoader
from src.utils import Config, get_metamodel_path


def main():
    """Load metamodel into Neo4j and generate embeddings."""
    parser = argparse.ArgumentParser(description='Setup and load the Neo4j graph from metamodel configuration')
    parser.add_argument(
        '--version',
        type=str,
        default=None,
        help='Version suffix for both schema and entities files (e.g., "v2" will load schema-v2.yaml and entities-v2.yaml)'
    )
    parser.add_argument(
        '--schema-version',
        type=str,
        default=None,
        help='Version suffix for schema file only (overrides --version for schema)'
    )
    parser.add_argument(
        '--entities-version',
        type=str,
        default=None,
        help='Version suffix for entities file only (overrides --version for entities)'
    )
    args = parser.parse_args()

    print("🚀 Starting graph setup...")

    # Determine which versions are being used
    schema_ver = args.schema_version if args.schema_version else args.version
    entities_ver = args.entities_version if args.entities_version else args.version

    if schema_ver and entities_ver:
        print(f"   Using schema version: {schema_ver}")
        print(f"   Using entities version: {entities_ver}")
    elif schema_ver or entities_ver:
        if schema_ver:
            print(f"   Using schema version: {schema_ver}")
        if entities_ver:
            print(f"   Using entities version: {entities_ver}")
    elif args.version:
        print(f"   Using metamodel version: {args.version}")

    # Load metamodel
    print("\n📖 Loading metamodel...")
    loader = MetamodelLoader(
        config_dir=get_metamodel_path(),
        version=args.version,
        schema_version=args.schema_version,
        entities_version=args.entities_version
    )
    schema = loader.load_schema()
    entities = loader.load_entities()

    print(f"   Schema version: {schema.get('version')}")
    print(f"   Node types: {', '.join(loader.get_node_types())}")
    print(f"   Relationship types: {', '.join(loader.get_relationship_types())}")

    # Load graph
    print("\n🔌 Connecting to Neo4j...")

    graph_loader = GraphLoader(
        uri=Config.NEO4J_URI,
        user=Config.NEO4J_USER,
        password=Config.NEO4J_PASSWORD
    )
    try:
        graph_loader.load_all(schema=schema, data=entities, clear_first=True, create_constraints=True, build_gds=True)
    finally:
        graph_loader.close()


    print("\n✨ Graph setup complete!")
    # print("   You can now run 'python scripts/index_embeddings.py' to create the search index.")


if __name__ == "__main__":
    main()
