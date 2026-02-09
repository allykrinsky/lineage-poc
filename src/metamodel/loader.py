"""Metamodel loading utilities."""
import yaml
from pathlib import Path
from typing import Dict, Any


class MetamodelLoader:
    """Loads and validates metamodel definitions."""

    def __init__(self, config_dir: str = "config/metamodel", version: str = None):
        """
        Initialize the metamodel loader.

        Args:
            config_dir: Directory containing metamodel configuration files
            version: Optional version suffix (e.g., 'v2' will load schema-v2.yaml and entities-v2.yaml)
        """
        self.config_dir = Path(config_dir)
        self.version = version

        # Construct filenames based on version
        if version:
            self.schema_path = self.config_dir / f"schema-{version}.yaml"
            self.entities_path = self.config_dir / f"entities-{version}.yaml"
        else:
            self.schema_path = self.config_dir / "schema.yaml"
            self.entities_path = self.config_dir / "entities.yaml"

    def load_schema(self) -> Dict[str, Any]:
        """
        Load the metamodel schema definition.

        Returns:
            Dictionary containing schema definition
        """
        with open(self.schema_path, "r") as f:
            return yaml.safe_load(f)

    def load_entities(self) -> Dict[str, Any]:
        """
        Load the metamodel entity data.

        Returns:
            Dictionary containing entity data (use_cases, models, datasets, attributes)
        """
        with open(self.entities_path, "r") as f:
            return yaml.safe_load(f)

    def load_all(self) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Load both schema and entity data.

        Returns:
            Tuple of (schema, entities)
        """
        return self.load_schema(), self.load_entities()

    def get_node_types(self) -> list[str]:
        """
        Get list of node types defined in schema.

        Returns:
            List of node type names
        """
        schema = self.load_schema()
        return list(schema.get("node_types", {}).keys())

    def get_relationship_types(self) -> list[str]:
        """
        Get list of relationship types defined in schema.

        Returns:
            List of relationship type names
        """
        schema = self.load_schema()
        return list(schema.get("relationship_types", {}).keys())
