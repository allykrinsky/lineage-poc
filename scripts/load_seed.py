#!/usr/bin/env python3
"""Load seed graph data from seed_graph.cypher into Neo4j."""

import sys
from pathlib import Path
from neo4j import GraphDatabase

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.utils import Config


def execute_cypher_file(driver, filepath: Path):
    """Execute Cypher statements from a file."""
    with open(filepath, 'r') as f:
        content = f.read()

    # Split by semicolons and execute each statement
    statements = []
    current = []

    for line in content.split('\n'):
        # Skip empty lines and comments
        stripped = line.strip()
        if not stripped or stripped.startswith('//'):
            continue

        current.append(line)

        if stripped.endswith(';'):
            stmt = '\n'.join(current)
            statements.append(stmt)
            current = []

    print(f"Found {len(statements)} statements to execute")

    with driver.session() as session:
        for i, stmt in enumerate(statements, 1):
            if not stmt.strip():
                continue

            try:
                session.run(stmt)
                if i % 20 == 0:
                    print(f"  Executed {i}/{len(statements)}...")
            except Exception as e:
                print(f"Warning: Statement {i} failed: {str(e)[:100]}")
                # Continue with remaining statements

    # Verify
    with driver.session() as session:
        result = session.run("MATCH (n) RETURN count(n) as count")
        node_count = result.single()['count']

        result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
        rel_count = result.single()['count']

        print(f"\n✅ Load complete!")
        print(f"   Nodes: {node_count}")
        print(f"   Relationships: {rel_count}")


def main():
    """Load seed data from seed_graph.cypher."""
    print("🚀 Loading seed graph data...\n")

    seed_file = Path(__file__).parent.parent / "seed_graph.cypher"
    if not seed_file.exists():
        print(f"❌ Seed file not found: {seed_file}")
        sys.exit(1)

    # Connect to Neo4j
    print(f"🔌 Connecting to Neo4j at {Config.NEO4J_URI}...")
    driver = GraphDatabase.driver(
        Config.NEO4J_URI,
        auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD)
    )

    try:
        execute_cypher_file(driver, seed_file)
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        sys.exit(1)
    finally:
        driver.close()

    print("\n✨ Seed data loaded successfully!")


if __name__ == '__main__':
    main()
