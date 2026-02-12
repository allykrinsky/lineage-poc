// =============================================================================
// Generic Lineage POC — Neo4j Seed Data
// =============================================================================
// This script creates a realistic graph that exercises all three axes:
//   X-axis (lineage): Dataset → ETL Job → Dataset → ETL Job → Model Version
//   Y-axis (hierarchy): Workspace → Dataset → Attributes, Model → Model Version
//   Z-axis (association): Use cases, workspaces, result sets, glossary terms
//
// Scenario:
//   A fraud detection model is trained on customer transaction data.
//   Raw data flows through ETL into a curated dataset, which feeds a training
//   job that produces a model version. The model is deployed via an agentic
//   system in a workspace. Data quality result sets are linked to key datasets.
//   Business glossary terms map to logical attributes.
// =============================================================================


// ─────────────────────────────────────────────
// 0. CLEAR EXISTING DATA (for reruns)
// ─────────────────────────────────────────────
MATCH (n) DETACH DELETE n;


// ─────────────────────────────────────────────
// 1. DATASETS (the core resources)
// ─────────────────────────────────────────────
CREATE (raw_txn:Dataset {
  id: 'ds-001',
  name: 'raw_transactions',
  sub_type: null,
  description: 'Raw credit card transaction feed from source system'
})

CREATE (curated_txn:Dataset {
  id: 'ds-002',
  name: 'curated_transactions',
  sub_type: null,
  description: 'Cleaned and enriched transaction data'
})

CREATE (feature_set:Dataset {
  id: 'ds-003',
  name: 'fraud_feature_set',
  sub_type: null,
  description: 'Engineered features for fraud model training'
})

CREATE (predictions:Dataset {
  id: 'ds-004',
  name: 'fraud_predictions',
  sub_type: null,
  description: 'Model prediction outputs'
})

CREATE (dq_results:Dataset {
  id: 'ds-005',
  name: 'txn_quality_results',
  sub_type: 'resultset',
  description: 'Data quality check results for curated_transactions'
})


// ─────────────────────────────────────────────
// 2. ATTRIBUTES (column-level, various sub-types)
// ─────────────────────────────────────────────

// Logical attributes (on curated_transactions)
CREATE (attr_acct:Attribute {
  id: 'attr-001',
  name: 'account_id',
  sub_type: 'logical',
  description: 'Customer account identifier'
})

CREATE (attr_amt:Attribute {
  id: 'attr-002',
  name: 'transaction_amount',
  sub_type: 'logical',
  description: 'Transaction amount in USD'
})

CREATE (attr_fraud_flag:Attribute {
  id: 'attr-003',
  name: 'is_fraud',
  sub_type: 'logical',
  description: 'Fraud label (target variable)'
})

// Conceptual attributes (on feature_set)
CREATE (attr_avg_txn:Attribute {
  id: 'attr-004',
  name: 'avg_transaction_30d',
  sub_type: 'conceptual',
  description: 'Average transaction amount over 30 days'
})

CREATE (attr_txn_freq:Attribute {
  id: 'attr-005',
  name: 'txn_frequency_7d',
  sub_type: 'conceptual',
  description: 'Transaction frequency in last 7 days'
})

// Term attributes (business glossary)
CREATE (term_acct:Attribute {
  id: 'attr-006',
  name: 'Account Identifier',
  sub_type: 'term',
  description: 'Business definition of account ID'
})

CREATE (term_fraud:Attribute {
  id: 'attr-007',
  name: 'Fraudulent Transaction',
  sub_type: 'term',
  description: 'Business definition of fraud classification'
})

// Report attribute
CREATE (rattr_fraud_rate:Attribute {
  id: 'attr-008',
  name: 'fraud_rate',
  sub_type: 'report',
  description: 'Calculated fraud rate metric'
})


// ─────────────────────────────────────────────
// 3. ETL JOBS (X-axis transformers)
// ─────────────────────────────────────────────
CREATE (job_ingest:ETLJob {
  id: 'job-001',
  name: 'ingest_raw_transactions',
  description: 'Ingests raw transaction data and writes to curated layer'
})

CREATE (job_feature:ETLJob {
  id: 'job-002',
  name: 'build_fraud_features',
  description: 'Feature engineering pipeline for fraud detection'
})

CREATE (job_train:ETLJob {
  id: 'job-003',
  name: 'train_fraud_model',
  description: 'Model training job — consumes feature set, produces model version'
})

CREATE (job_score:ETLJob {
  id: 'job-004',
  name: 'score_transactions',
  description: 'Batch scoring job — applies model to new transactions'
})


// ─────────────────────────────────────────────
// 4. DATA DEPENDENCIES (attribute-level transformers)
// ─────────────────────────────────────────────
CREATE (dep_acct_map:DataDependency {
  id: 'dep-001',
  name: 'account_id_passthrough',
  description: 'Maps account_id from curated to feature set'
})

CREATE (dep_avg_calc:DataDependency {
  id: 'dep-002',
  name: 'avg_txn_calculation',
  description: 'Computes avg_transaction_30d from transaction_amount'
})

CREATE (dep_freq_calc:DataDependency {
  id: 'dep-003',
  name: 'frequency_calculation',
  description: 'Computes txn_frequency_7d from transaction records'
})


// ─────────────────────────────────────────────
// 5. MODELS & VERSIONS
// ─────────────────────────────────────────────
CREATE (model_fraud:Model {
  id: 'model-001',
  name: 'fraud_detection_model',
  description: 'XGBoost-based fraud detection model'
})

CREATE (mv_v1:ModelVersion {
  id: 'mv-001',
  name: 'fraud_detection_v1.0',
  version: '1.0',
  description: 'Initial production version'
})

CREATE (mv_v2:ModelVersion {
  id: 'mv-002',
  name: 'fraud_detection_v2.0',
  version: '2.0',
  description: 'Retrained with expanded feature set'
})


// ─────────────────────────────────────────────
// 6. AGENTIC SYSTEM & AGENTS
// ─────────────────────────────────────────────
CREATE (asys:AgenticSystem {
  id: 'asys-001',
  name: 'fraud_review_system',
  description: 'Automated fraud case review system'
})

CREATE (asys_v1:AgenticSystemVersion {
  id: 'asysv-001',
  name: 'fraud_review_v1',
  version: '1.0'
})

CREATE (agent_v1:AgentVersion {
  id: 'agv-001',
  name: 'fraud_reviewer_agent_v1',
  description: 'Agent that reviews flagged transactions'
})


// ─────────────────────────────────────────────
// 7. APPLICATIONS, MCP, WORKSPACE
// ─────────────────────────────────────────────
CREATE (app_platform:Application {
  id: 'app-001',
  name: 'fraud_analytics_platform',
  description: 'Main fraud analytics application'
})

CREATE (mcp_srv:MCPServer {
  id: 'mcp-001',
  name: 'fraud_model_server',
  description: 'MCP server hosting fraud model endpoints'
})

CREATE (mcp_res:MCPResource {
  id: 'mcpr-001',
  name: 'fraud_score_endpoint',
  description: '/v1/score resource'
})

CREATE (mcp_tool:MCPTool {
  id: 'mcpt-001',
  name: 'fraud_lookup_tool',
  description: 'Tool for looking up fraud scores'
})

CREATE (ws:Workspace {
  id: 'ws-001',
  name: 'fraud_detection_workspace',
  description: 'Primary workspace for fraud detection team'
})

CREATE (ws_svc:WorkspaceService {
  id: 'wssvc-001',
  name: 'fraud_model_service',
  description: 'Service deploying fraud model in workspace'
})


// ─────────────────────────────────────────────
// 8. PROCESSES
// ─────────────────────────────────────────────
CREATE (proc_review:Process {
  id: 'proc-001',
  name: 'fraud_case_review',
  description: 'End-to-end fraud case review process'
})

CREATE (proc_sub:Process {
  id: 'proc-002',
  name: 'automated_triage',
  description: 'Automated triage sub-process'
})


// ─────────────────────────────────────────────
// 9. REPORTS
// ─────────────────────────────────────────────
CREATE (report_fraud:Report {
  id: 'rpt-001',
  name: 'weekly_fraud_report',
  description: 'Weekly fraud metrics dashboard'
})


// ─────────────────────────────────────────────
// 10. USE CASES
// ─────────────────────────────────────────────
CREATE (uc_fraud:UseCase {
  id: 'uc-001',
  name: 'fraud_detection',
  description: 'Fraud detection and prevention use case'
})

CREATE (uc_compliance:UseCase {
  id: 'uc-002',
  name: 'regulatory_compliance',
  description: 'Regulatory compliance and reporting'
})


// ─────────────────────────────────────────────
// 11. GLOSSARY & DATA CONCEPTS
// ─────────────────────────────────────────────
CREATE (gloss_main:Glossary {
  id: 'gloss-001',
  name: 'enterprise_glossary',
  description: 'Enterprise-wide business glossary'
})

CREATE (gloss_risk:Glossary {
  id: 'gloss-002',
  name: 'risk_glossary',
  description: 'Risk domain glossary'
})

CREATE (dc_customer:DataConcept {
  id: 'dc-001',
  name: 'Customer Identity',
  description: 'Conceptual grouping for customer identification attributes'
})

CREATE (df_txn_flow:DataFlow {
  id: 'df-001',
  name: 'transaction_data_flow',
  description: 'Data flow for transaction data pipeline'
})


// =============================================================================
// EDGES — X-AXIS (LINEAGE)
// =============================================================================

// Dataset-level lineage: raw → ingest job → curated → feature job → feature_set
CREATE (raw_txn)-[:IS_CONSUMED_BY]->(job_ingest)
CREATE (curated_txn)-[:DATASET_PRODUCED_BY]->(job_ingest)

// Semantic: job_ingest consumes raw_txn, produces curated_txn
// FIXED: Swapped edge names to match correct semantics
// - Input datasets use IS_CONSUMED_BY or DATASET_CONSUMED_BY
// - Output datasets use DATASET_PRODUCED_BY

CREATE (curated_txn)-[:IS_CONSUMED_BY]->(job_feature)
CREATE (feature_set)-[:DATASET_PRODUCED_BY]->(job_feature)

// Training lineage: feature_set → training job → model version
CREATE (feature_set)-[:IS_CONSUMED_BY {context: 'model_training'}]->(job_train)
CREATE (mv_v2)-[:DATASET_PRODUCED_BY]->(job_train)

// Scoring lineage: model version + curated data → scoring job → predictions
CREATE (mv_v2)-[:IS_CONSUMED_BY {context: 'inference'}]->(job_score)
CREATE (curated_txn)-[:IS_CONSUMED_BY {context: 'scoring_input'}]->(job_score)
CREATE (predictions)-[:DATASET_PRODUCED_BY]->(job_score)

// Attribute-level lineage via data dependencies
CREATE (dep_acct_map)-[:DATA_DEPENDENCY_PRODUCED_BY]->(attr_acct)
CREATE (dep_acct_map)-[:DATA_DEPENDENCY_CONSUMED_BY]->(attr_avg_txn)

CREATE (dep_avg_calc)-[:DATA_DEPENDENCY_PRODUCED_BY]->(attr_amt)
CREATE (dep_avg_calc)-[:DATA_DEPENDENCY_CONSUMED_BY]->(attr_avg_txn)

CREATE (dep_freq_calc)-[:DATA_DEPENDENCY_PRODUCED_BY]->(attr_acct)
CREATE (dep_freq_calc)-[:DATA_DEPENDENCY_CONSUMED_BY]->(attr_txn_freq)

// Model version → transforms → data dependency
CREATE (mv_v2)-[:TRANSFORMS]->(dep_avg_calc)
CREATE (mv_v2)-[:TRANSFORMS]->(dep_freq_calc)

// Data flow lineage
CREATE (df_txn_flow)-[:DATA_FLOW_PRODUCED_BY]->(app_platform)
CREATE (df_txn_flow)-[:DATAFLOW_CONSUMED_BY]->(app_platform)


// =============================================================================
// EDGES — Y-AXIS (HIERARCHY)
// =============================================================================

// Versioning
CREATE (asys)-[:HAS_VERSION]->(asys_v1)
CREATE (asys_v1)-[:HAS_MEMBER]->(agent_v1)
CREATE (model_fraud)-[:MODEL_TO_MODEL_VERSION]->(mv_v1)
CREATE (model_fraud)-[:MODEL_TO_MODEL_VERSION]->(mv_v2)

// Attribute containment
CREATE (attr_acct)-[:IS_ATTRIBUTE_FOR]->(curated_txn)
CREATE (attr_amt)-[:IS_ATTRIBUTE_FOR]->(curated_txn)
CREATE (attr_fraud_flag)-[:IS_ATTRIBUTE_FOR]->(curated_txn)
CREATE (attr_avg_txn)-[:IS_ATTRIBUTE_FOR]->(feature_set)
CREATE (attr_txn_freq)-[:IS_ATTRIBUTE_FOR]->(feature_set)
CREATE (rattr_fraud_rate)-[:ELEMENT_OF]->(report_fraud)

// Glossary hierarchy
CREATE (gloss_risk)-[:SUB_GLOSSARY_OF]->(gloss_main)
CREATE (gloss_risk)-[:BUSINESS_TERM_OF]->(term_fraud)
CREATE (gloss_main)-[:BUSINESS_TERM_OF]->(term_acct)
CREATE (gloss_main)-[:BUSINESS_ELEMENT_TERM_OF]->(term_fraud)

// MCP hierarchy
CREATE (mcp_srv)-[:PROVIDES_RESOURCE]->(mcp_res)
CREATE (mcp_srv)-[:PROVIDES_TOOL]->(mcp_tool)
CREATE (app_platform)-[:PRODUCED_BY]->(mcp_srv)

// Process hierarchy
CREATE (proc_sub)-[:SUB_PROCESS_OF]->(proc_review)

// Workspace / service hierarchy
CREATE (ws_svc)-[:INSTALLED]->(ws)
CREATE (report_fraud)-[:CREATED_BY]->(app_platform)

// Domain grouping (hierarchy)
CREATE (asys)-[:SYSTEM_USE_CASE]->(uc_fraud)
CREATE (model_fraud)-[:MODEL_USE_CASE]->(uc_fraud)


// =============================================================================
// EDGES — Z-AXIS (ASSOCIATION)
// =============================================================================

// Agent uses resources
CREATE (agent_v1)-[:USES]->(predictions)
CREATE (agent_v1)-[:USES]->(mcp_tool)
CREATE (agent_v1)-[:USES]->(mv_v2)

// Attribute term mappings
CREATE (attr_acct)-[:IS_MAPPED_TO]->(term_acct)
CREATE (attr_fraud_flag)-[:IS_MAPPED_TO]->(term_fraud)
CREATE (term_acct)-[:ALIASED_AS]->(term_fraud)   // contrived but tests term-to-term

// Data concept associations
CREATE (dc_customer)-[:DATA_CONCEPT_ATTRIBUTE]->(attr_avg_txn)
CREATE (dc_customer)-[:DATA_CONCEPT_ATTRIBUTE]->(term_acct)

// Result set associations (data quality)
CREATE (dq_results)-[:RESULTSETS_DATASET]->(curated_txn)
CREATE (dq_results)-[:RESULTSETS_REPORT]->(report_fraud)
CREATE (dq_results)-[:RESULTSETS_DATAFLOW]->(df_txn_flow)

// Use case / workspace associations
CREATE (uc_fraud)-[:USE_CASE_DATASET]->(feature_set)
CREATE (uc_fraud)-[:USE_CASE_DATASET]->(curated_txn)
CREATE (uc_compliance)-[:USE_CASE_DATASET]->(predictions)
CREATE (ws)-[:WORKSPACE_USE_CASE]->(uc_fraud)
CREATE (ws)-[:WORKSPACE_DATASET]->(curated_txn)
CREATE (ws)-[:WORKSPACE_DATASET]->(feature_set)

// Workspace service association
CREATE (ws_svc)-[:IMPLEMENTS]->(mv_v2);


// =============================================================================
// VERIFICATION QUERIES (run after seeding)
// =============================================================================

// Count by axis
// MATCH ()-[r]->()
// WITH type(r) as edge_type, count(*) as cnt
// RETURN edge_type, cnt ORDER BY edge_type;

// Count nodes by label
// MATCH (n)
// WITH labels(n)[0] as label, count(*) as cnt
// RETURN label, cnt ORDER BY label;
