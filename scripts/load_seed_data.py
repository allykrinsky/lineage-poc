"""
Load seed data from seed_graph.cypher into Neo4j.

This script reads the Cypher file and executes it against Neo4j.
"""

from neo4j import GraphDatabase
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from src.utils import Config


def load_seed_data():
    """Load seed data from seed_graph.cypher"""
    # Read the Cypher file
    seed_file = Path(__file__).parent.parent / "seed_graph.cypher"

    if not seed_file.exists():
        print(f"ERROR: Seed file not found at {seed_file}")
        return False

    with open(seed_file, 'r') as f:
        cypher_script = f.read()

    # Split into individual statements (split by semicolon, ignoring commented lines)
    statements = []
    current_statement = []

    for line in cypher_script.split('\n'):
        # Skip comment lines
        if line.strip().startswith('//'):
            continue

        # Skip empty lines
        if not line.strip():
            continue

        current_statement.append(line)

        # Check if line ends with semicolon
        if line.strip().endswith(';'):
            statement = '\n'.join(current_statement)
            statements.append(statement)
            current_statement = []

    # Add any remaining statement
    if current_statement:
        statement = '\n'.join(current_statement)
        if statement.strip():
            statements.append(statement)

    print(f"Parsed {len(statements)} Cypher statements from seed file")

    # Connect to Neo4j and execute statements
    driver = GraphDatabase.driver(
        Config.NEO4J_URI,
        auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD)
    )

    try:
        with driver.session() as session:
            for i, statement in enumerate(statements):
                if not statement.strip():
                    continue

                try:
                    session.run(statement)
                    if (i + 1) % 10 == 0:
                        print(f"Executed {i + 1}/{len(statements)} statements...")
                except Exception as e:
                    print(f"Error executing statement {i + 1}:")
                    print(f"Statement: {statement[:100]}...")
                    print(f"Error: {e}")
                    # Continue with other statements

            # Verify data was loaded
            result = session.run("MATCH (n) RETURN count(n) as count")
            count = result.single()['count']
            print(f"\n✓ Successfully loaded seed data")
            print(f"✓ Total nodes in graph: {count}")

            # Show breakdown by label
            result = session.run("""
                MATCH (n)
                WITH labels(n)[0] as label, count(*) as cnt
                RETURN label, cnt
                ORDER BY cnt DESC
            """)

            print("\nNode counts by type:")
            for record in result:
                print(f"  {record['label']}: {record['cnt']}")

            return True

    except Exception as e:
        print(f"ERROR: Failed to connect to Neo4j: {e}")
        print(f"URI: {Config.NEO4J_URI}")
        print(f"User: {Config.NEO4J_USER}")
        return False
    finally:
        driver.close()


if __name__ == '__main__':
    success = load_seed_data()
    sys.exit(0 if success else 1)
