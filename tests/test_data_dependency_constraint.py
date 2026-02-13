"""
Tests for data dependency constraint validation.

Validates that data dependencies cannot connect attributes within the same dataset.
"""

import pytest
import yaml
from pathlib import Path
from src.graph.loader import GraphLoader, DataValidationError
from src.utils import Config


@pytest.fixture
def invalid_entities_data():
    """
    Create test data with a data dependency that violates the cross-dataset constraint.
    """
    return {
        "assets": {
            "Dataset": [
                {"id": "test-ds-001", "name": "test_dataset", "sub_type": None, "description": "Test dataset"}
            ],
            "Attribute": [
                {"id": "test-attr-001", "name": "field_a", "sub_type": "logical", "description": "Field A"},
                {"id": "test-attr-002", "name": "field_b", "sub_type": "logical", "description": "Field B"}
            ],
            "DataDependency": [
                {
                    "id": "test-dep-001",
                    "name": "invalid_same_dataset_dependency",
                    "description": "INVALID: Both attributes in same dataset"
                }
            ]
        },
        "relationships": [
            # Attributes belong to same dataset
            {"type": "IS_ATTRIBUTE_FOR", "from": "test-attr-001", "to": "test-ds-001"},
            {"type": "IS_ATTRIBUTE_FOR", "from": "test-attr-002", "to": "test-ds-001"},

            # Data dependency connects them (INVALID - same dataset)
            {"type": "DATA_DEPENDENCY_PRODUCED_BY", "from": "test-dep-001", "to": "test-attr-001"},
            {"type": "DATA_DEPENDENCY_CONSUMED_BY", "from": "test-dep-001", "to": "test-attr-002"}
        ]
    }


@pytest.fixture
def valid_entities_data():
    """
    Create test data with a data dependency that follows the cross-dataset constraint.
    """
    return {
        "assets": {
            "Dataset": [
                {"id": "test-ds-001", "name": "source_dataset", "sub_type": None, "description": "Source"},
                {"id": "test-ds-002", "name": "target_dataset", "sub_type": None, "description": "Target"}
            ],
            "Attribute": [
                {"id": "test-attr-001", "name": "field_a", "sub_type": "logical", "description": "Source field"},
                {"id": "test-attr-002", "name": "field_b", "sub_type": "logical", "description": "Target field"}
            ],
            "DataDependency": [
                {
                    "id": "test-dep-001",
                    "name": "valid_cross_dataset_dependency",
                    "description": "VALID: Attributes in different datasets"
                }
            ]
        },
        "relationships": [
            # Attributes belong to DIFFERENT datasets
            {"type": "IS_ATTRIBUTE_FOR", "from": "test-attr-001", "to": "test-ds-001"},
            {"type": "IS_ATTRIBUTE_FOR", "from": "test-attr-002", "to": "test-ds-002"},

            # Data dependency connects them (VALID - different datasets)
            {"type": "DATA_DEPENDENCY_PRODUCED_BY", "from": "test-dep-001", "to": "test-attr-001"},
            {"type": "DATA_DEPENDENCY_CONSUMED_BY", "from": "test-dep-001", "to": "test-attr-002"}
        ]
    }


@pytest.fixture
def schema_data():
    """Load the schema."""
    schema_path = Path("metamodel/schema-v2.yaml")
    with open(schema_path) as f:
        return yaml.safe_load(f)


class TestDataDependencyConstraint:
    """Tests for data dependency cross-dataset constraint"""

    def test_same_dataset_dependency_blocked(self, schema_data, invalid_entities_data):
        """
        Test that data dependencies within the same dataset are blocked.

        This should raise a DataValidationError when attempting to load.
        """
        loader = GraphLoader(
            Config.NEO4J_URI,
            Config.NEO4J_USER,
            Config.NEO4J_PASSWORD
        )

        with pytest.raises(DataValidationError) as exc_info:
            loader.load_all(
                schema=schema_data,
                data=invalid_entities_data,
                clear_first=True,
                create_constraints=False,
                build_gds=False
            )

        # Verify error message mentions the constraint
        error_message = str(exc_info.value)
        assert "Data Dependency Constraint Violations" in error_message
        assert "test-dep-001" in error_message
        assert "same dataset" in error_message.lower()

        print("\n✅ Same-dataset dependency correctly blocked")

    def test_cross_dataset_dependency_allowed(self, schema_data, valid_entities_data):
        """
        Test that data dependencies across different datasets are allowed.

        This should load successfully.
        """
        loader = GraphLoader(
            Config.NEO4J_URI,
            Config.NEO4J_USER,
            Config.NEO4J_PASSWORD
        )

        try:
            # Should not raise
            loader.load_all(
                schema=schema_data,
                data=valid_entities_data,
                clear_first=True,
                create_constraints=False,
                build_gds=False
            )

            # Verify the dependency was created
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(
                Config.NEO4J_URI,
                auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD)
            )

            with driver.session() as session:
                result = session.run("""
                    MATCH (dep:DataDependency {id: 'test-dep-001'})
                    MATCH (dep)-[:DATA_DEPENDENCY_PRODUCED_BY]->(src_attr:Attribute)
                    MATCH (dep)-[:DATA_DEPENDENCY_CONSUMED_BY]->(tgt_attr:Attribute)
                    MATCH (src_attr)-[:IS_ATTRIBUTE_FOR]->(src_ds:Dataset)
                    MATCH (tgt_attr)-[:IS_ATTRIBUTE_FOR]->(tgt_ds:Dataset)
                    RETURN src_ds.id as source_dataset, tgt_ds.id as target_dataset
                """)

                record = result.single()
                assert record is not None, "Dependency should exist"
                assert record['source_dataset'] == 'test-ds-001'
                assert record['target_dataset'] == 'test-ds-002'

            driver.close()

            print("\n✅ Cross-dataset dependency correctly allowed")
            print(f"   Source: test-ds-001")
            print(f"   Target: test-ds-002")

        finally:
            # Clean up test data
            loader.clear_graph()

    def test_production_data_follows_constraint(self):
        """
        Verify that the production entities-v2.yaml follows the constraint.

        This ensures existing data is compliant.
        """
        entities_path = Path("metamodel/entities-v2.yaml")
        with open(entities_path) as f:
            data = yaml.safe_load(f)

        # Build attribute → dataset mapping
        attr_to_dataset = {}
        for rel in data['relationships']:
            if rel.get('type') == 'IS_ATTRIBUTE_FOR':
                attr_to_dataset[rel['from']] = rel['to']

        # Check each data dependency
        violations = []
        for dep in data['assets']['DataDependency']:
            dep_id = dep['id']

            # Find source and target attributes
            source_attrs = []
            target_attrs = []

            for rel in data['relationships']:
                if rel.get('from') == dep_id:
                    if rel.get('type') == 'DATA_DEPENDENCY_PRODUCED_BY':
                        source_attrs.append(rel['to'])
                    elif rel.get('type') == 'DATA_DEPENDENCY_CONSUMED_BY':
                        target_attrs.append(rel['to'])

            # Get datasets
            source_datasets = {attr_to_dataset.get(attr) for attr in source_attrs if attr in attr_to_dataset}
            target_datasets = {attr_to_dataset.get(attr) for attr in target_attrs if attr in attr_to_dataset}

            # Check for overlap (same dataset)
            overlap = source_datasets & target_datasets
            if overlap:
                violations.append({
                    'dependency': dep_id,
                    'name': dep.get('name'),
                    'datasets': overlap,
                    'source_attrs': source_attrs,
                    'target_attrs': target_attrs
                })

        if violations:
            error_msg = "Production data has constraint violations:\n"
            for v in violations:
                error_msg += f"\n  {v['dependency']} ({v['name']})"
                error_msg += f"\n    Same dataset: {v['datasets']}"
                error_msg += f"\n    Sources: {v['source_attrs']}"
                error_msg += f"\n    Targets: {v['target_attrs']}"
            pytest.fail(error_msg)

        print(f"\n✅ All {len(data['assets']['DataDependency'])} production data dependencies follow cross-dataset constraint")
