# Synthetic Data Generation Rules

## Purpose

This document defines **practical validity rules** for generating synthetic graph data. These constraints go beyond what `metamodel/schema.yaml` allows structurally — the schema permits many relationships that are technically valid but semantically nonsensical. Follow these rules when generating `metamodel/entities.yaml` or any test fixtures.

**Rule of thumb:** If a relationship is allowed by the schema but not described here, do not generate it unless you have an explicit reason.

---

## Job Patterns

Jobs are X-axis transformer nodes. They consume inputs and produce outputs. Every Job must fall into one of these four patterns:

### ETL Job

Produces a Dataset from a Dataset.

| Direction | Resource Type | Sub-Type | Cardinality | Required |
|-----------|--------------|----------|-------------|----------|
| Input | Dataset | `null` | 1 or many | **Yes** |
| Input | Dataset | `null` | 1 | **Yes** |

**Invalid examples:**
- ETL job with no Dataset input
- ETL job with a `resultset` or `knowledge_base` Dataset as input

### Training Job

Produces a Model Version from a Dataset, optionally fine-tuning an existing model.

| Direction | Resource Type | Sub-Type | Cardinality | Required |
|-----------|--------------|----------|-------------|----------|
| Input | Dataset | `null` | Exactly 1 | **Yes** |
| Input | Model Version | — | 0 or 1 | No (if present, this is a fine-tune) |
| Output | Model Version | — | Exactly 1 | **Yes** |
| Association | Dataset | `resultset` | 0 or 1 | No |

**Invalid examples:**
- Training job with no Dataset input
- Training job with 2 Dataset inputs
- Training job that outputs a Dataset
- Training job with a `resultset` or `knowledge_base` Dataset as input

### RAG Job

Builds a knowledge base by combining datasets with a model for retrieval-augmented generation.

| Direction | Resource Type | Sub-Type | Cardinality | Required |
|-----------|--------------|----------|-------------|----------|
| Input | Dataset | `null` | 1 or many | **Yes** |
| Input | Model Version | — | Exactly 1 | **Yes** |
| Output | Dataset | `knowledge_base` | Exactly 1 | **Yes** |
| Association | Dataset | `resultset` | 0 or 1 | No |

**Invalid examples:**
- RAG job with no Model Version input
- RAG job that outputs a Model Version
- RAG job that outputs a Dataset with `null` sub-type
- RAG job with a `knowledge_base` Dataset as input

### Inference Job

Applies a model to a dataset to produce predictions or enriched output.

| Direction | Resource Type | Sub-Type | Cardinality | Required |
|-----------|--------------|----------|-------------|----------|
| Input | Dataset | `null` | Exactly 1 | **Yes** |
| Input | Model Version | — | Exactly 1 | **Yes** |
| Output | Dataset | `null` | Exactly 1 | **Yes** |
| Association | Dataset | `resultset` | 0 or 1 | No |

**Invalid examples:**
- Inference job with no Model Version input
- Inference job that outputs a Model Version
- Inference job with multiple Dataset inputs (that's a RAG job)

### General Job Rules

- **Every Job must have at least one input and exactly one output.** No orphan jobs.
- **Lineage edges on ETL Jobs use specific edge names based on direction:**
  - Input to job: `DATASET_PRODUCED_BY` (dataset→job) or `IS_CONSUMED_BY` (dataset/model_version→job)
  - Output from job: `DATASET_CONSUMED_BY` (dataset→job)

---

## Data Dependency Pattern

Data Dependencies are X-axis transformer nodes at the **attribute level**. They represent column-level transformations.

| Direction | Resource Type | Sub-Type | Cardinality | Required |
|-----------|--------------|----------|-------------|----------|
| Input | Attribute | `conceptual` or `logical` | 1 or many | **Yes** |
| Output | Attribute | **must match input sub-type** | 1 or many | **Yes** |
| Association | Model Version | — | 0 or 1 | No |

**Critical constraint:** All input attributes and all output attributes of a single Data Dependency must share the same `sub_type`. You cannot have a Data Dependency that takes `logical` attributes as input and produces `conceptual` attributes as output.

**Invalid examples:**
- Data Dependency with no input attributes
- Data Dependency with no output attributes
- Data Dependency with `logical` input and `conceptual` output
- Data Dependency with a Dataset as input or output (those connect at the job level, not dependency level)
- Data Dependency with a `term` or `report` attribute as input or output (terms are glossary concepts, report attributes belong to reports — neither participates in data transformation)

---

## Attribute Rules

Attributes have three sub-types: `logical`, `conceptual`, and `term`. There is no separate `report` attribute sub-type — logical attributes serve both datasets and reports.

### Logical Attributes

These are the primary data attributes. They can live on **either** a Dataset or a Report, but exactly one — never both, never neither.

- **Must** have exactly one parent: either `IS_ATTRIBUTE_FOR` → Dataset (sub_type: `null`) **or** `ELEMENT_OF` → Report
- **Cannot** have both an `IS_ATTRIBUTE_FOR` and an `ELEMENT_OF` relationship
- **Cannot** exist standalone (no orphan attributes)
- **Cannot** belong to a Dataset with sub_type `resultset` or `knowledge_base`
- **Can** participate in Data Dependencies (X-axis lineage) regardless of whether they belong to a Dataset or Report
- **Can** map to `term` attributes via `IS_MAPPED_TO` (Z-axis)

### Conceptual Attributes

These are higher-level data attributes that represent conceptual definitions of data elements. They live on Datasets only.

- **Must** have exactly one `IS_ATTRIBUTE_FOR` → Dataset (sub_type: `null`)
- **Cannot** exist standalone (no orphan attributes)
- **Cannot** belong to a Dataset with sub_type `resultset` or `knowledge_base`
- **Cannot** belong to a Report (only logical attributes can)
- **Can** participate in Data Dependencies (X-axis lineage)
- **Cannot** map to `term` attributes via `IS_MAPPED_TO` (only logical can)

### Term Attributes

These are business glossary terms. They do **not** live on datasets or reports.

- **Must** belong to a Glossary via `BUSINESS_TERM_OF` or `BUSINESS_ELEMENT_TERM_OF` (Y-axis)
- **Cannot** have an `IS_ATTRIBUTE_FOR` or `ELEMENT_OF` relationship
- **Cannot** participate in Data Dependencies (not transformation participants)
- **Can** be aliased to other `term` attributes via `ALIASED_AS` (Z-axis, term→term only)
- **Can** be linked from `logical` attributes via `IS_MAPPED_TO` (Z-axis, logical→term only)
- **Can** be linked from Data Concepts via `DATA_CONCEPT_ATTRIBUTE` (Z-axis)

### Attribute Parentage Summary

| Sub-Type | Parent Via | Parent Type | Can Do Lineage | Can Map to Term |
|----------|-----------|-------------|---------------|-----------------|
| `logical` | `IS_ATTRIBUTE_FOR` **or** `ELEMENT_OF` | Dataset (null) **or** Report (exactly one) | Yes (Data Dependency) | Yes (`IS_MAPPED_TO`) |
| `conceptual` | `IS_ATTRIBUTE_FOR` | Dataset (null) only | Yes (Data Dependency) | No |
| `term` | `BUSINESS_TERM_OF` / `BUSINESS_ELEMENT_TERM_OF` | Glossary | No | N/A (is the term) |

---

## Dataset Sub-Type Rules

| Sub-Type | Can Have Attributes | Can Be ETL Input | Can Be ETL Output | Can Be Result Set Association | Role |
|----------|-------------------|-----------------|-------------------|-------------------------------|------|
| `null` (standard) | **Yes** (logical, conceptual) | Yes | Yes (from ingestion/feature jobs) | No | Core tabular data |
| `resultset` | **No** | No | No | Yes (Z-axis association to jobs) | Data quality results container |
| `knowledge_base` | **No** | No (not as primary input) | Yes (from RAG/inference jobs) | No | RAG/inference output |

---

## Glossary Rules

- Glossaries form a hierarchy via `SUB_GLOSSARY_OF` (Y-axis). A child glossary points up to its parent.
- Glossaries contain `term` attributes via `BUSINESS_TERM_OF` and `BUSINESS_ELEMENT_TERM_OF`.
- Glossaries do **not** contain `logical`, `conceptual`, or `report` attributes.
- A `term` attribute must belong to exactly one Glossary. No orphan terms.

### Glossary Mapping Direction Constraints

These are strict — the Z-axis mappings between attributes are directional and type-constrained:

| Edge | Source | Destination | Direction |
|------|--------|-------------|-----------|
| `IS_MAPPED_TO` | Attribute (`logical` only) | Attribute (`term` only) | logical → term |
| `ALIASED_AS` | Attribute (`term` only) | Attribute (`term` only) | term → term |
| `DATA_CONCEPT_ATTRIBUTE` | Data Concept | Attribute (`conceptual` or `term` only) | concept → attribute |

**Invalid mapping examples:**
- `conceptual` attribute → `IS_MAPPED_TO` → `term` (only logical can map to term)
- `term` → `IS_MAPPED_TO` → `logical` (wrong direction)
- `logical` → `ALIASED_AS` → `logical` (aliased_as is term-to-term only)
- Data Concept → `DATA_CONCEPT_ATTRIBUTE` → `logical` attribute (data concepts link to conceptual or term only)

---

## Model & Model Version Rules

- **Every Model Version must belong to a Model** via `MODEL_TO_MODEL_VERSION` (Y-axis). No standalone Model Versions.
- A Model can have multiple Model Versions (versioning).
- Models belong to Use Cases via `MODEL_USE_CASE` (Y-axis).
- Model Versions participate in X-axis lineage as inputs/outputs of ETL Jobs and can associate with Data Dependencies via `TRANSFORMS`.
- Model Versions do **not** directly connect to Datasets outside of ETL Job context — the job is always the intermediary.

---

## Agentic System Hierarchy Rules

The agentic system hierarchy is **strict and sequential**. The chain must be complete:

```
AgenticSystem → AgenticSystemVersion → AgentVersion
```

- **Agentic System** must have at least one Agentic System Version (via `HAS_VERSION`).
- **Agentic System Version** must belong to exactly one Agentic System.
- **Agentic System Version** can contain Agent Versions and/or other Agentic System Versions (via `HAS_MEMBER`).
- **Agent Version** must belong to exactly one Agentic System Version.
- **Agent Versions are pure Z-axis consumers.** They `USES` datasets, MCP tools, and model versions. They do **not** participate in X-axis lineage — they never produce or consume via ETL Jobs.
- Agentic Systems belong to Use Cases via `SYSTEM_USE_CASE` (Y-axis).

**Invalid examples:**
- Agent Version with no parent Agentic System Version
- Agent Version directly under an Agentic System (must go through a version)
- Agent Version with a `DATASET_PRODUCED_BY` or `IS_CONSUMED_BY` edge (agents don't do ETL)
- Standalone Agentic System Version with no parent system

---

## MCP Hierarchy Rules

The MCP hierarchy is also **strict**:

```
Application → MCPServer → MCPResource / MCPTool
```

- **MCP Server** must be produced by an Application (via `PRODUCED_BY`). No standalone servers.
- **MCP Resource** must belong to an MCP Server (via `PROVIDES_RESOURCE`). No standalone resources.
- **MCP Tool** must belong to an MCP Server (via `PROVIDES_TOOL`). No standalone tools.
- MCP Tools are consumed by Agent Versions via `USES` (Z-axis).

**Invalid examples:**
- MCP Tool with no parent MCP Server
- MCP Server with no parent Application
- MCP Resource directly under an Application (must go through a server)

---

## Report Rules

- **Every Report must be created by an Application** via `CREATED_BY` (Y-axis). No standalone reports.
- Reports contain `report` sub-type attributes via `ELEMENT_OF`.
- Reports do **not** contain `logical`, `conceptual`, or `term` attributes.
- Reports can be associated with Result Set Datasets via `RESULTSETS_REPORT` (Z-axis).

---

## Data Flow Rules

Data Flows represent **inter-application data movement**, not dataset transformation. They are distinct from ETL pipelines.

- Data Flows connect to Applications via `DATA_FLOW_PRODUCED_BY` and `DATAFLOW_CONSUMED_BY` (X-axis).
- Data Flows do **not** connect to ETL Jobs or Datasets directly.
- Data Flows can be associated with Result Set Datasets via `RESULTSETS_DATAFLOW` (Z-axis).

**Do not conflate Data Flows with ETL pipelines.** A Data Flow describes the movement of data between applications (e.g., API feeds, file transfers). ETL Jobs describe the transformation of datasets.

---

## Process Rules

- Processes can have sub-processes via `SUB_PROCESS_OF` (Y-axis) — child points up to parent.
- Processes can have instances via `INSTANCE_OF` (Y-axis) — instance points up to definition.
- **`INSTANCE_OF` and `SUB_PROCESS_OF` mean different things.** An instance is a running copy of a process definition. A sub-process is a child step within a parent process. Do not use them interchangeably.
- Processes connect to Datasets via the `PROCESS_DATASET` passthrough node (Y-axis, structural).
- Processes can be associated with Result Set Datasets via `RESULTSETS_PROCESS` (Z-axis).

---

## Workspace Rules

- **Workspace Services must be installed in a Workspace** via `INSTALLED` (Y-axis). No standalone services.
- Workspace Services can depend on other Workspace Services via `DEPENDS_ON` (Y-axis).
- Workspace Services can implement a Model Version via `IMPLEMENTS` (Z-axis).
- Workspaces associate with Datasets via `WORKSPACE_DATASET` (Z-axis).
- Workspaces associate with Use Cases via `WORKSPACE_USE_CASE` (Z-axis).

---

## Result Set Rules

Result Set Datasets (`sub_type: resultset`) are data quality containers. They are **Z-axis only** — they connect to other resources via association, never via lineage.

- Result Sets associate with Datasets via `RESULTSETS_DATASET`
- Result Sets associate with Reports via `RESULTSETS_REPORT`
- Result Sets associate with Data Flows via `RESULTSETS_DATAFLOW`
- Result Sets associate with Processes via `RESULTSETS_PROCESS`
- Result Sets are **never** produced or consumed by ETL Jobs
- Result Sets **cannot** have Attributes

---

## Use Case & Data Concept Rules

### Use Cases
- Use Cases are qualifier nodes that group related resources.
- Models belong to Use Cases via `MODEL_USE_CASE` (Y-axis).
- Agentic Systems belong to Use Cases via `SYSTEM_USE_CASE` (Y-axis).
- Use Cases associate with Datasets via `USE_CASE_DATASET` (Z-axis).
- Workspaces associate with Use Cases via `WORKSPACE_USE_CASE` (Z-axis).
- Use Cases do not have their own hierarchy — they are flat grouping nodes.

### Data Concepts
- Data Concepts are standalone qualifier nodes — they do not require a parent or container.
- Data Concepts link to `conceptual` or `term` attributes via `DATA_CONCEPT_ATTRIBUTE` (Z-axis).
- Data Concepts do **not** link to `logical` or `report` attributes.

---

## Orphan Node Prevention

**No node should exist in the graph without at least one relationship.** Every node type has a required minimum:

| Node Type | Minimum Required Relationship |
|-----------|-------------------------------|
| Dataset (null) | At least 1 ETL Job connection (input or output) |
| Dataset (resultset) | At least 1 `RESULTSETS_*` association |
| Dataset (knowledge_base) | Must be output of a RAG or Inference Job |
| Attribute (logical/conceptual) | Exactly 1 `IS_ATTRIBUTE_FOR` → Dataset (null) |
| Attribute (term) | Exactly 1 `BUSINESS_TERM_OF` or `BUSINESS_ELEMENT_TERM_OF` → Glossary |
| Attribute (report) | Exactly 1 `ELEMENT_OF` → Report |
| ETL Job | At least 1 input + exactly 1 output |
| Data Dependency | At least 1 input attribute + at least 1 output attribute |
| Model | At least 1 Model Version |
| Model Version | Exactly 1 parent Model |
| Agentic System | At least 1 Agentic System Version |
| Agentic System Version | Exactly 1 parent Agentic System |
| Agent Version | Exactly 1 parent Agentic System Version |
| MCP Server | Exactly 1 parent Application |
| MCP Resource | Exactly 1 parent MCP Server |
| MCP Tool | Exactly 1 parent MCP Server |
| Report | Exactly 1 `CREATED_BY` → Application |
| Workspace Service | Exactly 1 `INSTALLED` → Workspace |
| Process | At least 1 relationship (sub-process, instance, or dataset link) |
| Glossary | At least 1 term or sub-glossary |
| Use Case | At least 1 associated resource |
| Data Concept | At least 1 `DATA_CONCEPT_ATTRIBUTE` link |

---

## Example: Valid Fraud Detection Pipeline

```
# Standard Datasets (sub_type: null) — these have attributes
raw_transactions (Dataset, sub_type: null)
  └─ account_id (Attribute, sub_type: logical)
  └─ transaction_amount (Attribute, sub_type: logical)

curated_transactions (Dataset, sub_type: null)
  └─ account_id (Attribute, sub_type: logical)
  └─ amount_cleaned (Attribute, sub_type: logical)

# ETL: Ingestion (standard dataset → standard dataset)
ingest_job (ETLJob)
  Input:  raw_transactions (Dataset, null)         ✅
  Output: curated_transactions (Dataset, null)     ✅

# ETL: Training (dataset + optional model → new model version)
train_job (ETLJob)
  Input:  curated_transactions (Dataset, null)     ✅
  Input:  fraud_model_v1 (ModelVersion)            ✅ (fine-tune)
  Output: fraud_model_v2 (ModelVersion)            ✅

# Model hierarchy
fraud_model (Model)
  └─ fraud_model_v1 (ModelVersion)                 ✅ parent via MODEL_TO_MODEL_VERSION
  └─ fraud_model_v2 (ModelVersion)                 ✅ parent via MODEL_TO_MODEL_VERSION

# ETL: Inference (dataset + model → knowledge base)
score_job (ETLJob)
  Input:  curated_transactions (Dataset, null)     ✅
  Input:  fraud_model_v2 (ModelVersion)            ✅
  Output: fraud_predictions (Dataset, knowledge_base) ✅

# Data quality result set — Z-axis association only
txn_quality_results (Dataset, sub_type: resultset)
  Association → curated_transactions               ✅ (via RESULTSETS_DATASET)
  Attributes: NONE                                 ✅

# Knowledge base output — no attributes
fraud_predictions (Dataset, sub_type: knowledge_base)
  Attributes: NONE                                 ✅

# Attribute-level lineage — same sub_type in and out
dep_amount_cleanup (DataDependency)
  Input:  transaction_amount (Attribute, logical)  ✅
  Output: amount_cleaned (Attribute, logical)      ✅ (same sub_type)

# Glossary — terms live here, not on datasets
risk_glossary (Glossary)
  └─ sub_glossary_of → enterprise_glossary         ✅
  └─ "Fraudulent Transaction" (Attribute, term)    ✅ via BUSINESS_TERM_OF

# Term mapping — logical → term only
account_id (Attribute, logical) → IS_MAPPED_TO → "Account ID" (Attribute, term) ✅

# Agentic system — full chain required
fraud_review_system (AgenticSystem)
  └─ fraud_review_v1 (AgenticSystemVersion)        ✅
     └─ fraud_agent_v1 (AgentVersion)              ✅
        └─ USES → fraud_predictions (Dataset)      ✅ Z-axis only
        └─ USES → fraud_lookup_tool (MCPTool)      ✅ Z-axis only

# MCP hierarchy — full chain required
fraud_platform (Application)
  └─ PRODUCED_BY → fraud_server (MCPServer)        ✅
     └─ PROVIDES_TOOL → fraud_lookup_tool          ✅
     └─ PROVIDES_RESOURCE → score_endpoint         ✅

# Report — must have application parent
weekly_fraud_report (Report)
  └─ CREATED_BY → fraud_platform (Application)     ✅
  └─ fraud_rate (Attribute, report)                ✅ via ELEMENT_OF
```

## Example: Invalid Patterns (Do NOT Generate)

```
# ❌ Attribute on a resultset dataset
quality_results (Dataset, sub_type: resultset)
  └─ check_name (Attribute)                        ❌ resultsets can't have attributes

# ❌ Attribute on a knowledge_base dataset
fraud_predictions (Dataset, sub_type: knowledge_base)
  └─ score (Attribute)                             ❌ knowledge bases can't have attributes

# ❌ Training job outputting a dataset
train_job (ETLJob)
  Input:  features (Dataset, null)
  Output: predictions (Dataset, null)              ❌ training jobs output Model Versions

# ❌ Data dependency with mixed sub-types
dep_cross_type (DataDependency)
  Input:  logical_attr (Attribute, logical)
  Output: conceptual_attr (Attribute, conceptual)  ❌ must be same sub_type

# ❌ Term attribute in a data dependency
dep_with_term (DataDependency)
  Input:  "Account ID" (Attribute, term)           ❌ terms don't do lineage
  Output: some_attr (Attribute, term)              ❌

# ❌ Standalone attribute
orphan_attr (Attribute, logical)                   ❌ not attached to any dataset

# ❌ Term attribute on a dataset
transactions (Dataset, sub_type: null)
  └─ "Account ID" (Attribute, term)                ❌ terms belong to glossaries

# ❌ Logical attribute on a report
weekly_report (Report)
  └─ account_id (Attribute, logical)               ❌ reports have report attributes only

# ❌ Resultset as ETL input
score_job (ETLJob)
  Input:  quality_results (Dataset, resultset)     ❌ resultsets are Z-axis only
  Output: predictions (Dataset, knowledge_base)

# ❌ RAG job with no model
rag_job (ETLJob)
  Input:  documents (Dataset, null)
  Output: kb (Dataset, knowledge_base)             ❌ RAG requires a Model Version input

# ❌ Conceptual attribute mapped to term
concept_attr (Attribute, conceptual) → IS_MAPPED_TO → term  ❌ only logical can map to term

# ❌ Agent version producing data via ETL
fraud_agent (AgentVersion)
  → DATASET_PRODUCED_BY → some_job (ETLJob)        ❌ agents are Z-axis consumers only

# ❌ Standalone MCP Tool
fraud_tool (MCPTool)                               ❌ must belong to an MCP Server

# ❌ Agent Version without system chain
fraud_agent (AgentVersion)                         ❌ must have AgenticSystemVersion parent

# ❌ Standalone Model Version
fraud_v3 (ModelVersion)                            ❌ must belong to a Model

# ❌ Report with no application
orphan_report (Report)                             ❌ must have CREATED_BY → Application

# ❌ Data Concept linked to logical attribute
customer_concept (DataConcept)
  → DATA_CONCEPT_ATTRIBUTE → account_id (logical)  ❌ data concepts link to conceptual or term only

# ❌ Data flow connected to ETL job
txn_flow (DataFlow)
  → DATASET_PRODUCED_BY → ingest_job (ETLJob)      ❌ data flows connect to Applications only
```