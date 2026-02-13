"""Metamodel loading utilities."""
import yaml
from pathlib import Path
from typing import Dict, Any


class MetamodelLoader:
    """Loads and validates metamodel definitions."""

    def __init__(self, config_dir: str = "config/metamodel", version: str = None, schema_version: str = None, entities_version: str = None):
        """
        Initialize the metamodel loader.

        Args:
            config_dir: Directory containing metamodel configuration files
            version: Optional version suffix for both files (e.g., 'v2' will load schema-v2.yaml and entities-v2.yaml)
            schema_version: Optional version suffix for schema file only (overrides version for schema)
            entities_version: Optional version suffix for entities file only (overrides version for entities)
        """
        self.config_dir = Path(config_dir)
        self.version = version

        # Determine schema version (schema_version takes precedence over version)
        schema_ver = schema_version if schema_version is not None else version
        # Determine entities version (entities_version takes precedence over version)
        entities_ver = entities_version if entities_version is not None else version

        # Construct filenames based on versions
        if schema_ver:
            self.schema_path = self.config_dir / f"schema-{schema_ver}.yaml"
        else:
            self.schema_path = self.config_dir / "schema.yaml"

        if entities_ver:
            self.entities_path = self.config_dir / f"entities-{entities_ver}.yaml"
        else:
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
