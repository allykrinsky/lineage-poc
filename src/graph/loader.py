"""Schema-driven Neo4j graph loading operations (metamodel + instance data)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Set, Optional
from neo4j import GraphDatabase

# -----------------------------
# Schema parsing + validation
# -----------------------------

@dataclass(frozen=True)
class PropertySpec:
    name: str
    type: str
    required: bool = False
    unique: bool = False
    allowed_values: Optional[List[Any]] = None


class SchemaError(ValueError):
    pass


class DataValidationError(ValueError):
    pass


def _safe_ident(name: str) -> str:
    """
    Allow only simple Neo4j identifiers for labels/relationship types.
    Prevents Cypher injection when we interpolate labels/types.
    """
    if not name or not all(c.isalnum() or c == "_" for c in name):
        raise SchemaError(f"Unsafe identifier: {name!r}")
    return name


def _coerce_type(value: Any, expected: str) -> bool:
    """Lightweight runtime type checks for schema validation."""
    if value is None:
        return True
    expected = expected.lower()
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected in ("int", "integer"):
        return isinstance(value, int) and not isinstance(value, bool)
    if expected in ("float", "double", "decimal", "number"):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    # Allow unvalidated types (date/datetime/etc.) since YAML -> python may vary
    return True


class Metamodel:
    """
    Parsed metamodel schema providing:
      - node type -> property specs
      - allowed relationship types with (from_type, to_type)
    """

    def __init__(self, schema: Dict[str, Any]):
        self.raw = schema
        self.node_types: Dict[str, Dict[str, PropertySpec]] = {}
        self.required_props: Dict[str, Set[str]] = {}
        self.allowed_values: Dict[Tuple[str, str], Set[Any]] = {}
        self.relationships: Dict[str, Set[Tuple[str, str]]] = {}

        self._parse()

    def _parse(self) -> None:
        node_types = self.raw.get("node_types") or {}
        if not isinstance(node_types, dict) or not node_types:
            raise SchemaError("Schema missing 'node_types' or it's empty.")

        for node_label, node_def in node_types.items():
            label = _safe_ident(node_label)
            props = node_def.get("properties") or []
            if not isinstance(props, list):
                raise SchemaError(f"node_types.{label}.properties must be a list")

            prop_map: Dict[str, PropertySpec] = {}
            req: Set[str] = set()

            for p in props:
                if not isinstance(p, dict):
                    raise SchemaError(f"Invalid property spec in {label}: {p!r}")
                name = p.get("name")
                if not name:
                    raise SchemaError(f"Property missing name in {label}")
                spec = PropertySpec(
                    name=name,
                    type=p.get("type", "string"),
                    required=bool(p.get("required", False)),
                    unique=bool(p.get("unique", False)),
                    allowed_values=p.get("allowed_values"),
                )
                prop_map[name] = spec
                if spec.required:
                    req.add(name)
                if spec.allowed_values is not None:
                    self.allowed_values[(label, name)] = set(spec.allowed_values)

            # Strongly expect an id field for MERGE keys
            if "id" not in prop_map:
                raise SchemaError(f"Node type {label} must define an 'id' property.")
            if not prop_map["id"].required:
                raise SchemaError(f"Node type {label} 'id' must be required: true.")

            self.node_types[label] = prop_map
            self.required_props[label] = req

        rels = self.raw.get("relationships") or []
        if not isinstance(rels, list):
            raise SchemaError("Schema 'relationships' must be a list.")

        for r in rels:
            if not isinstance(r, dict):
                raise SchemaError(f"Invalid relationship spec: {r!r}")
            rtype = _safe_ident(r.get("type", ""))
            frm = _safe_ident(r.get("from", ""))
            to = _safe_ident(r.get("to", ""))
            if frm not in self.node_types or to not in self.node_types:
                raise SchemaError(f"Relationship {rtype} references unknown node types {frm}->{to}")
            self.relationships.setdefault(rtype, set()).add((frm, to))

    def labels(self) -> List[str]:
        return list(self.node_types.keys())

    def relationship_types(self) -> List[str]:
        return list(self.relationships.keys())


# -----------------------------
# Loader
# -----------------------------

class GraphLoader:
    """Loads schema-validated metamodel instance data into Neo4j."""

    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def clear_graph(self):
        print("🧨 Clearing graph...")
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    # ---- Validation helpers ----

    def _validate_assets(self, mm: Metamodel, data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        assets = data.get("assets") or {}
        if not isinstance(assets, dict):
            raise DataValidationError("Instance data must contain 'assets' as a mapping of NodeType -> list[objects].")

        # Ensure only schema labels are present (or at least validate those that are)
        normalized: Dict[str, List[Dict[str, Any]]] = {}
        seen_ids: Dict[Tuple[str, str], bool] = {}

        for label, items in assets.items():
            label = _safe_ident(label)
            if label not in mm.node_types:
                raise DataValidationError(f"Unknown node type in assets: {label}")

            if not isinstance(items, list):
                raise DataValidationError(f"assets.{label} must be a list")

            prop_specs = mm.node_types[label]
            required = mm.required_props[label]
            allowed_value_map = {k: v for (l, k), v in mm.allowed_values.items() if l == label}

            out_items: List[Dict[str, Any]] = []
            for obj in items:
                if not isinstance(obj, dict):
                    raise DataValidationError(f"assets.{label} contains a non-object: {obj!r}")

                # required fields
                missing = [p for p in required if p not in obj or obj[p] in (None, "")]
                if missing:
                    raise DataValidationError(f"{label} missing required properties: {missing}. Offending object: {obj}")

                # validate types + allowed values (only for properties present)
                for k, v in obj.items():
                    if k not in prop_specs:
                        # allow extra properties? you can flip this to error if you want strict
                        continue
                    spec = prop_specs[k]
                    if not _coerce_type(v, spec.type):
                        raise DataValidationError(
                            f"{label}.{k} expected {spec.type}, got {type(v).__name__}. Offending object id={obj.get('id')}"
                        )
                    if k in allowed_value_map and v is not None and v not in allowed_value_map[k]:
                        raise DataValidationError(
                            f"{label}.{k} has invalid value {v!r}. Allowed: {sorted(list(allowed_value_map[k]))}. id={obj.get('id')}"
                        )

                # unique id per label within the batch
                _id = obj.get("id")
                key = (label, _id)
                if key in seen_ids:
                    raise DataValidationError(f"Duplicate id in assets for {label}: {_id}")
                seen_ids[key] = True

                out_items.append(obj)

            normalized[label] = out_items

        return normalized

    def _index_assets_by_id(self, assets: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
        idx: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for label, objs in assets.items():
            idx[label] = {o["id"]: o for o in objs}
        return idx

    def _validate_relationships(
        self,
        mm: Metamodel,
        assets: Dict[str, List[Dict[str, Any]]],
        data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        rels = data.get("relationships") or []
        if not isinstance(rels, list):
            raise DataValidationError("Instance data must contain 'relationships' as a list.")

        idx = self._index_assets_by_id(assets)

        validated: List[Dict[str, Any]] = []
        for r in rels:
            if not isinstance(r, dict):
                raise DataValidationError(f"Relationship must be an object: {r!r}")

            rtype = _safe_ident(r.get("type", ""))
            from_id = r.get("from")
            to_id = r.get("to")
            if not rtype or from_id is None or to_id is None:
                raise DataValidationError(f"Relationship missing fields (type/from/to): {r}")

            if rtype not in mm.relationships:
                raise DataValidationError(f"Unknown relationship type: {rtype}")

            # infer endpoint labels by scanning assets index
            from_labels = [lbl for lbl, by_id in idx.items() if from_id in by_id]
            to_labels = [lbl for lbl, by_id in idx.items() if to_id in by_id]

            if len(from_labels) != 1:
                raise DataValidationError(f"Relationship from id {from_id!r} not found uniquely in assets (found in {from_labels}).")
            if len(to_labels) != 1:
                raise DataValidationError(f"Relationship to id {to_id!r} not found uniquely in assets (found in {to_labels}).")

            from_label = from_labels[0]
            to_label = to_labels[0]

            if (from_label, to_label) not in mm.relationships[rtype]:
                allowed_pairs = sorted(list(mm.relationships[rtype]))
                raise DataValidationError(
                    f"Relationship {rtype} disallowed for {from_label}->{to_label}. Allowed: {allowed_pairs}"
                )

            validated.append(
                {
                    "type": rtype,
                    "from_label": from_label,
                    "to_label": to_label,
                    "from_id": from_id,
                    "to_id": to_id,
                }
            )

        return validated

    # ---- Neo4j write helpers ----

    def create_constraints(self, mm: Metamodel):
        """Create uniqueness constraints on :Label(id) for all schema node types (Neo4j 5 syntax)."""
        print("🧷 Ensuring uniqueness constraints on (label.id)...")
        with self.driver.session() as session:
            for label in mm.labels():
                # constraint name must be unique; keep it stable
                cname = f"uniq_{label}_id"
                # Neo4j doesn't allow parameterized label in schema commands, so interpolate after validation
                cypher = f"CREATE CONSTRAINT {cname} IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE"
                session.run(cypher)

    def create_nodes(self, mm: Metamodel, assets: Dict[str, List[Dict[str, Any]]]):
        """Create/merge nodes for all labels present in assets."""
        print("📦 Creating nodes...")
        with self.driver.session() as session:
            for label, rows in assets.items():
                if not rows:
                    continue
                label = _safe_ident(label)

                # Only set known schema properties (ignore extras)
                schema_props = mm.node_types[label].keys()
                cleaned_rows = []
                for r in rows:
                    cleaned = {k: v for k, v in r.items() if k in schema_props}
                    cleaned_rows.append(cleaned)

                # MERGE on id, then set remaining props
                # We set all props in one go: SET n += row (keeps id consistent)
                cypher = f"""
                UNWIND $rows AS row
                MERGE (n:{label} {{id: row.id}})
                SET n += row
                """
                session.run(cypher, {"rows": cleaned_rows})
                print(f"  ✅ {label}: {len(rows)}")

    def create_relationships(self, rels: List[Dict[str, Any]]):
        """Create relationships after nodes exist."""
        print("🔗 Creating relationships...")
        with self.driver.session() as session:
            # group by (type, from_label, to_label) so we can UNWIND per group (fast)
            buckets: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
            for r in rels:
                key = (r["type"], r["from_label"], r["to_label"])
                buckets.setdefault(key, []).append({"from_id": r["from_id"], "to_id": r["to_id"]})

            for (rtype, from_label, to_label), rows in buckets.items():
                rtype = _safe_ident(rtype)
                from_label = _safe_ident(from_label)
                to_label = _safe_ident(to_label)

                cypher = f"""
                UNWIND $rows AS row
                MATCH (a:{from_label} {{id: row.from_id}})
                MATCH (b:{to_label} {{id: row.to_id}})
                MERGE (a)-[:{rtype}]->(b)
                """
                session.run(cypher, {"rows": rows})
                print(f"  ✅ {from_label}-[:{rtype}]->{to_label}: {len(rows)}")

    def build_gds_projection(self, mm: Metamodel, projection_name: str = "domainGraph"):
        """
        Build GDS projection dynamically from schema node labels + relationship types.
        Assumes all relationships are projected undirected for embedding-type use cases.
        """
        print("📐 Building GDS projection...")
        labels = mm.labels()
        rel_types = mm.relationship_types()

        with self.driver.session() as session:
            # Drop if exists (ignore errors)
            session.run(
                "CALL gds.graph.drop($name, false) YIELD graphName RETURN graphName",
                {"name": projection_name},
            )

            rel_map = {rtype: {"orientation": "UNDIRECTED"} for rtype in rel_types}

            session.run(
                """
                CALL gds.graph.project($name, $labels, $rels)
                """,
                {"name": projection_name, "labels": labels, "rels": rel_map},
            )
            print(f"✅ GDS projection '{projection_name}' built with labels={labels} rels={rel_types}")

    def load_all(
        self,
        schema: Dict[str, Any],
        data: Dict[str, Any],
        clear_first: bool = True,
        create_constraints: bool = True,
        build_gds: bool = False,
        projection_name: str = "domainGraph",
    ):
        """
        Complete graph loading pipeline using schema validation.

        schema: metamodel YAML loaded to dict (contains node_types + relationships)
        data: instance YAML loaded to dict (contains assets + relationships)
        """
        mm = Metamodel(schema)

        if clear_first:
            self.clear_graph()

        if create_constraints:
            self.create_constraints(mm)

        assets = self._validate_assets(mm, data)
        rels = self._validate_relationships(mm, assets, data)

        self.create_nodes(mm, assets)
        self.create_relationships(rels)

        if build_gds:
            self.build_gds_projection(mm, projection_name=projection_name)

        print("🎉 Graph load complete!")





# """Neo4j graph loading operations."""
# from typing import Dict, Any
# from neo4j import GraphDatabase


# class GraphLoader:
#     """Handles loading metamodel data into Neo4j."""

#     def __init__(self, uri: str, user: str, password: str):
#         """
#         Initialize the graph loader.

#         Args:
#             uri: Neo4j connection URI
#             user: Neo4j username
#             password: Neo4j password
#         """
#         self.driver = GraphDatabase.driver(uri, auth=(user, password))

#     def close(self):
#         """Close the Neo4j driver connection."""
#         self.driver.close()

#     def clear_graph(self):
#         """Clear all nodes and relationships from the graph."""
#         print("🧨 Clearing graph...")
#         with self.driver.session() as session:
#             session.run("MATCH (n) DETACH DELETE n")

#     def create_nodes(self, data: Dict[str, Any]):
#         """
#         Create nodes from metamodel data.

#         Args:
#             data: Dictionary containing use_cases, models, datasets, and attributes
#         """
#         with self.driver.session() as session:
#             print("📦 Creating Use Case nodes...")
#             for uc in data.get("use_cases", []):
#                 session.run("""
#                     CREATE (n:UseCase {
#                         id: $id, title: $title, description: $description, tags: $tags
#                     })
#                 """, uc)

#             print("📦 Creating Model nodes...")
#             for m in data.get("models", []):
#                 session.run("""
#                     CREATE (n:Model {
#                         id: $id, title: $title, tags: $tags
#                     })
#                 """, m)

#             print("📦 Creating Dataset nodes...")
#             for ds in data.get("datasets", []):
#                 session.run("""
#                     CREATE (n:Dataset {
#                         id: $id, title: $title, tags: $tags
#                     })
#                 """, ds)

#             print("📦 Creating Attribute nodes...")
#             for a in data.get("attributes", []):
#                 session.run("""
#                     CREATE (n:Attribute {
#                         id: $id, name: $name
#                     })
#                 """, a)

#     def create_relationships(self, data: Dict[str, Any]):
#         """
#         Create relationships between nodes.

#         Args:
#             data: Dictionary containing use_cases, models, datasets, and attributes
#         """
#         print("🔗 Creating relationships...")
#         with self.driver.session() as session:
#             # USE_CASE -> MODEL
#             for uc in data.get("use_cases", []):
#                 for m in uc.get("uses_models", []):
#                     session.run("""
#                         MATCH (u:UseCase {id: $uc}), (m:Model {id: $m})
#                         CREATE (u)-[:USES_MODEL]->(m)
#                     """, {"uc": uc["id"], "m": m})

#             # USE_CASE -> DATASET
#             for uc in data.get("use_cases", []):
#                 for ds in uc.get("consumes_datasets", []):
#                     session.run("""
#                         MATCH (u:UseCase {id: $uc}), (d:Dataset {id: $ds})
#                         CREATE (u)-[:CONSUMES_DATA]->(d)
#                     """, {"uc": uc["id"], "ds": ds})

#             # MODEL -> DATASET
#             for m in data.get("models", []):
#                 for ds in m.get("trained_on", []):
#                     session.run("""
#                         MATCH (m:Model {id: $m}), (d:Dataset {id: $ds})
#                         CREATE (m)-[:TRAINED_ON]->(d)
#                     """, {"m": m["id"], "ds": ds})

#             # DATASET -> ATTRIBUTE
#             for a in data.get("attributes", []):
#                 for ds in a.get("datasets", []):
#                     session.run("""
#                         MATCH (a:Attribute {id: $a}), (d:Dataset {id: $ds})
#                         CREATE (d)-[:HAS_ATTRIBUTE]->(a)
#                     """, {"a": a["id"], "ds": ds})

#     def build_gds_projection(self, projection_name: str = "domainGraph"):
#         """
#         Build GDS graph projection and generate Node2Vec embeddings.

#         Args:
#             projection_name: Name for the GDS projection
#         """
#         with self.driver.session() as session:
#             print("📐 Dropping old GDS graph...")
#             session.run(
#                 "CALL gds.graph.drop($name, false) YIELD graphName RETURN graphName",
#                 {"name": projection_name}
#             )

#             print("📐 Building GDS projection...")
#             session.run(f"""
#                 CALL gds.graph.project(
#                     '{projection_name}',
#                     ['UseCase', 'Model', 'Dataset', 'Attribute'],
#                     {{
#                         USES_MODEL: {{orientation: 'UNDIRECTED'}},
#                         TRAINED_ON: {{orientation: 'UNDIRECTED'}},
#                         CONSUMES_DATA: {{orientation: 'UNDIRECTED'}},
#                         HAS_ATTRIBUTE: {{orientation: 'UNDIRECTED'}}
#                     }}
#                 )
#             """)

#             print("⚡ Running Node2Vec...")
#             session.run(f"""
#                 CALL gds.node2vec.write('{projection_name}', {{
#                     embeddingDimension: 64,
#                     walkLength: 80,
#                     iterations: 10,
#                     returnFactor: 1.0,
#                     inOutFactor: 1.0,
#                     writeProperty: 'n2v'
#                 }})
#             """)

#             print("✅ Node2Vec embeddings generated.")

#     def load_all(self, data: Dict[str, Any], clear_first: bool = True):
#         """
#         Complete graph loading pipeline.

#         Args:
#             data: Metamodel entity data
#             clear_first: Whether to clear existing graph first
#         """
#         if clear_first:
#             self.clear_graph()

#         self.create_nodes(data)
#         self.create_relationships(data)
#         self.build_gds_projection()

#         print("🎉 Graph load complete!")
