"""
Generate large-scale sample data following data_generation_rules.md

This script extends entities-large.yaml to reach ~1000 nodes
"""
import yaml
from typing import Dict, List, Any

# Load existing data
with open('metamodel/entities-large.yaml') as f:
    base_data = yaml.safe_load(f)

# Count current nodes
def count_nodes(data: Dict[str, Any]) -> int:
    total = 0
    for node_type, items in data['assets'].items():
        if isinstance(items, list):
            total += len(items)
    return total

current_count = count_nodes(base_data)
print(f"Current node count: {current_count}")
print(f"Target: ~1000 nodes")
print(f"Need to generate: ~{1000 - current_count} more nodes\n")

# Calculate what to generate
# We'll expand each domain with more pipelines
domains = {
    'payment': 'Payment Processing',
    'inventory': 'Inventory Management',
    'shipping': 'Shipping & Logistics',
    'support': 'Customer Support',
    'sales': 'Sales Analytics',
    'operations': 'Operations',
    'finance': 'Finance',
    'hr': 'Human Resources'
}

# Generate additional datasets, attributes, jobs, etc.
new_assets = {
    'Dataset': [],
    'Attribute': [],
    'Job': [],
    'DataDependency': [],
    'Model': [],
    'ModelVersion': [],
    'AgenticSystem': [],
    'AgenticSystemVersion': [],
    'AgentVersion': [],
    'Application': [],
    'MCPServer': [],
    'MCPResource': [],
    'MCPTool': [],
    'Workspace': [],
    'WorkspaceService': [],
    'Report': [],
    'UseCase': [],
    'Glossary': [],
    'DataConcept': [],
    'DataFlow': [],
    'Process': []
}

new_relationships = []

# Counter for IDs
counters = {}

def get_id(prefix: str) -> str:
    if prefix not in counters:
        counters[prefix] = 1
    else:
        counters[prefix] += 1
    return f"{prefix}-{counters[prefix]:03d}"

# Generate datasets and pipelines for new domains
for domain_key, domain_name in domains.items():
    print(f"Generating {domain_name} domain...")

    # Use case
    uc_id = get_id(f"{domain_key}-uc")
    new_assets['UseCase'].append({
        'id': uc_id,
        'name': f"{domain_name.lower().replace(' ', '_')}",
        'description': f"{domain_name} use case"
    })

    # Application
    app_id = get_id(f"{domain_key}-app")
    new_assets['Application'].append({
        'id': app_id,
        'name': f"{domain_name.lower().replace(' ', '_')}_platform",
        'description': f"{domain_name} platform"
    })

    # MCP Server
    mcp_id = get_id(f"{domain_key}-mcp")
    new_assets['MCPServer'].append({
        'id': mcp_id,
        'name': f"{domain_key}_api_server",
        'description': f"{domain_name} API server"
    })
    new_relationships.append({
        'type': 'PRODUCED_BY',
        'from': app_id,
        'to': mcp_id
    })

    # MCP Resource
    mcpr_id = get_id(f"{domain_key}-mcpr")
    new_assets['MCPResource'].append({
        'id': mcpr_id,
        'name': f"{domain_key}_api_endpoint",
        'description': f"/v1/{domain_key}/data"
    })
    new_relationships.append({
        'type': 'PROVIDES_RESOURCE',
        'from': mcp_id,
        'to': mcpr_id
    })

    # MCP Tools
    for tool_num in range(1, 3):
        mcpt_id = get_id(f"{domain_key}-mcpt")
        new_assets['MCPTool'].append({
            'id': mcpt_id,
            'name': f"{domain_key}_tool_{tool_num}",
            'description': f"{domain_name} tool {tool_num}"
        })
        new_relationships.append({
            'type': 'PROVIDES_TOOL',
            'from': mcp_id,
            'to': mcpt_id
        })

    # Workspace
    ws_id = get_id(f"{domain_key}-ws")
    new_assets['Workspace'].append({
        'id': ws_id,
        'name': f"{domain_key}_workspace",
        'description': f"{domain_name} team workspace"
    })
    new_relationships.append({
        'type': 'WORKSPACE_USE_CASE',
        'from': ws_id,
        'to': uc_id
    })

    # Glossary
    gloss_id = get_id(f"{domain_key}-gloss")
    new_assets['Glossary'].append({
        'id': gloss_id,
        'name': f"{domain_key}_glossary",
        'description': f"{domain_name} terminology"
    })
    new_relationships.append({
        'type': 'SUB_GLOSSARY_OF',
        'from': gloss_id,
        'to': 'gloss-001'  # Enterprise glossary
    })

    # Terms
    for term_num in range(1, 4):
        term_id = get_id(f"{domain_key}-term")
        new_assets['Attribute'].append({
            'id': term_id,
            'name': f"{domain_name} Term {term_num}",
            'sub_type': 'term',
            'description': f"Business term {term_num} for {domain_name}"
        })
        new_relationships.append({
            'type': 'BUSINESS_TERM_OF',
            'from': gloss_id,
            'to': term_id
        })

    # Data Concept
    dc_id = get_id(f"{domain_key}-dc")
    new_assets['DataConcept'].append({
        'id': dc_id,
        'name': f"{domain_name} Metrics",
        'description': f"{domain_name} key metrics"
    })

    # Data Flow
    df_id = get_id(f"{domain_key}-df")
    new_assets['DataFlow'].append({
        'id': df_id,
        'name': f"{domain_key}_data_flow",
        'description': f"{domain_name} data movement"
    })
    new_relationships.append({
        'type': 'DATA_FLOW_PRODUCED_BY',
        'from': df_id,
        'to': app_id
    })
    new_relationships.append({
        'type': 'DATAFLOW_CONSUMED_BY',
        'from': df_id,
        'to': app_id
    })

    # Create 3 ETL pipelines per domain
    for pipeline_num in range(1, 4):
        # Raw dataset
        raw_ds_id = get_id(f"{domain_key}-ds")
        new_assets['Dataset'].append({
            'id': raw_ds_id,
            'name': f"raw_{domain_key}_data_{pipeline_num}",
            'sub_type': None,
            'description': f"Raw {domain_name} data source {pipeline_num}"
        })

        # Attributes for raw dataset
        for attr_num in range(1, 6):
            attr_id = get_id(f"{domain_key}-attr")
            new_assets['Attribute'].append({
                'id': attr_id,
                'name': f"{domain_key}_field_{pipeline_num}_{attr_num}",
                'sub_type': 'logical',
                'description': f"Field {attr_num} from raw {domain_name} data"
            })
            new_relationships.append({
                'type': 'IS_ATTRIBUTE_FOR',
                'from': attr_id,
                'to': raw_ds_id
            })

        # Curated dataset
        curated_ds_id = get_id(f"{domain_key}-ds")
        new_assets['Dataset'].append({
            'id': curated_ds_id,
            'name': f"curated_{domain_key}_data_{pipeline_num}",
            'sub_type': None,
            'description': f"Curated {domain_name} data {pipeline_num}"
        })

        # Attributes for curated dataset
        for attr_num in range(1, 5):
            attr_id = get_id(f"{domain_key}-attr")
            new_assets['Attribute'].append({
                'id': attr_id,
                'name': f"{domain_key}_clean_field_{pipeline_num}_{attr_num}",
                'sub_type': 'logical',
                'description': f"Cleaned field {attr_num}"
            })
            new_relationships.append({
                'type': 'IS_ATTRIBUTE_FOR',
                'from': attr_id,
                'to': curated_ds_id
            })

        # ETL Job
        job_id = get_id(f"{domain_key}-job")
        new_assets['Job'].append({
            'id': job_id,
            'name': f"ingest_{domain_key}_{pipeline_num}",
            'sub_type': 'etl',
            'description': f"Ingest and clean {domain_name} data {pipeline_num}"
        })
        new_relationships.append({
            'type': 'IS_CONSUMED_BY',
            'from': raw_ds_id,
            'to': job_id
        })
        new_relationships.append({
            'type': 'DATASET_PRODUCED_BY',
            'from': curated_ds_id,
            'to': job_id
        })

        # Data Dependencies
        for dep_num in range(1, 3):
            dep_id = get_id(f"{domain_key}-dep")
            new_assets['DataDependency'].append({
                'id': dep_id,
                'name': f"{domain_key}_transformation_{pipeline_num}_{dep_num}",
                'description': f"Data transformation {dep_num}"
            })

        # Link workspace to dataset
        new_relationships.append({
            'type': 'WORKSPACE_DATASET',
            'from': ws_id,
            'to': curated_ds_id
        })

        # Result set
        if pipeline_num == 1:
            rs_id = get_id(f"{domain_key}-ds")
            new_assets['Dataset'].append({
                'id': rs_id,
                'name': f"{domain_key}_quality_results",
                'sub_type': 'resultset',
                'description': f"{domain_name} data quality results"
            })
            new_relationships.append({
                'type': 'RESULTSETS_DATASET',
                'from': rs_id,
                'to': curated_ds_id
            })
            new_relationships.append({
                'type': 'RESULTSETS_DATAFLOW',
                'from': rs_id,
                'to': df_id
            })

        # Feature dataset (for pipeline 2)
        if pipeline_num == 2:
            feature_ds_id = get_id(f"{domain_key}-ds")
            new_assets['Dataset'].append({
                'id': feature_ds_id,
                'name': f"{domain_key}_feature_set",
                'sub_type': None,
                'description': f"{domain_name} feature engineering"
            })

            # Conceptual attributes for features
            for attr_num in range(1, 4):
                attr_id = get_id(f"{domain_key}-attr")
                new_assets['Attribute'].append({
                    'id': attr_id,
                    'name': f"{domain_key}_feature_{attr_num}",
                    'sub_type': 'conceptual',
                    'description': f"Engineered feature {attr_num}"
                })
                new_relationships.append({
                    'type': 'IS_ATTRIBUTE_FOR',
                    'from': attr_id,
                    'to': feature_ds_id
                })

            # Feature engineering job
            feature_job_id = get_id(f"{domain_key}-job")
            new_assets['Job'].append({
                'id': feature_job_id,
                'name': f"build_{domain_key}_features",
                'sub_type': 'etl',
                'description': f"Build {domain_name} features"
            })
            new_relationships.append({
                'type': 'IS_CONSUMED_BY',
                'from': curated_ds_id,
                'to': feature_job_id
            })
            new_relationships.append({
                'type': 'DATASET_PRODUCED_BY',
                'from': feature_ds_id,
                'to': feature_job_id
            })

            # ML Model
            model_id = get_id(f"{domain_key}-model")
            new_assets['Model'].append({
                'id': model_id,
                'name': f"{domain_key}_prediction_model",
                'description': f"{domain_name} ML model"
            })
            new_relationships.append({
                'type': 'MODEL_USE_CASE',
                'from': model_id,
                'to': uc_id
            })

            # Model Version
            mv_id = get_id(f"{domain_key}-mv")
            new_assets['ModelVersion'].append({
                'id': mv_id,
                'name': f"{domain_key}_model_v1.0",
                'version': '1.0',
                'description': f"{domain_name} model v1"
            })
            new_relationships.append({
                'type': 'MODEL_TO_MODEL_VERSION',
                'from': model_id,
                'to': mv_id
            })

            # Training job
            train_job_id = get_id(f"{domain_key}-job")
            new_assets['Job'].append({
                'id': train_job_id,
                'name': f"train_{domain_key}_model",
                'sub_type': 'training',
                'description': f"Train {domain_name} model"
            })
            new_relationships.append({
                'type': 'IS_CONSUMED_BY',
                'from': feature_ds_id,
                'to': train_job_id,
                'properties': {'context': 'training_data'}
            })
            new_relationships.append({
                'type': 'DATASET_PRODUCED_BY',
                'from': mv_id,
                'to': train_job_id
            })

            # Predictions dataset (knowledge base)
            pred_ds_id = get_id(f"{domain_key}-ds")
            new_assets['Dataset'].append({
                'id': pred_ds_id,
                'name': f"{domain_key}_predictions",
                'sub_type': 'knowledge_base',
                'description': f"{domain_name} model predictions"
            })

            # Inference job
            inf_job_id = get_id(f"{domain_key}-job")
            new_assets['Job'].append({
                'id': inf_job_id,
                'name': f"score_{domain_key}_data",
                'sub_type': 'inference',
                'description': f"Score {domain_name} data"
            })
            new_relationships.append({
                'type': 'IS_CONSUMED_BY',
                'from': curated_ds_id,
                'to': inf_job_id,
                'properties': {'context': 'scoring_input'}
            })
            new_relationships.append({
                'type': 'IS_CONSUMED_BY',
                'from': mv_id,
                'to': inf_job_id,
                'properties': {'context': 'scoring_model'}
            })
            new_relationships.append({
                'type': 'DATASET_PRODUCED_BY',
                'from': pred_ds_id,
                'to': inf_job_id
            })

            # Link use case to feature dataset
            new_relationships.append({
                'type': 'USE_CASE_DATASET',
                'from': uc_id,
                'to': feature_ds_id
            })

            # Workspace service implementing model
            wssvc_id = get_id(f"{domain_key}-wssvc")
            new_assets['WorkspaceService'].append({
                'id': wssvc_id,
                'name': f"{domain_key}_model_service",
                'description': f"{domain_name} model serving"
            })
            new_relationships.append({
                'type': 'INSTALLED',
                'from': wssvc_id,
                'to': ws_id
            })
            new_relationships.append({
                'type': 'IMPLEMENTS',
                'from': wssvc_id,
                'to': mv_id
            })

    # Agentic System
    asys_id = get_id(f"{domain_key}-asys")
    new_assets['AgenticSystem'].append({
        'id': asys_id,
        'name': f"{domain_key}_automation_system",
        'description': f"{domain_name} automation agents"
    })
    new_relationships.append({
        'type': 'SYSTEM_USE_CASE',
        'from': asys_id,
        'to': uc_id
    })

    # Agentic System Version
    asysv_id = get_id(f"{domain_key}-asysv")
    new_assets['AgenticSystemVersion'].append({
        'id': asysv_id,
        'name': f"{domain_key}_automation_v1",
        'version': '1.0'
    })
    new_relationships.append({
        'type': 'HAS_VERSION',
        'from': asys_id,
        'to': asysv_id
    })

    # Agent Versions
    for agent_num in range(1, 3):
        agv_id = get_id(f"{domain_key}-agv")
        new_assets['AgentVersion'].append({
            'id': agv_id,
            'name': f"{domain_key}_agent_{agent_num}",
            'description': f"{domain_name} agent {agent_num}"
        })
        new_relationships.append({
            'type': 'HAS_MEMBER',
            'from': asysv_id,
            'to': agv_id
        })

    # Report
    rpt_id = get_id(f"{domain_key}-rpt")
    new_assets['Report'].append({
        'id': rpt_id,
        'name': f"{domain_key}_dashboard",
        'description': f"{domain_name} metrics dashboard"
    })
    new_relationships.append({
        'type': 'CREATED_BY',
        'from': rpt_id,
        'to': app_id
    })

    # Report attributes
    for rpt_attr_num in range(1, 4):
        rpt_attr_id = get_id(f"{domain_key}-rpt-attr")
        new_assets['Attribute'].append({
            'id': rpt_attr_id,
            'name': f"{domain_key}_kpi_{rpt_attr_num}",
            'sub_type': 'logical',
            'description': f"{domain_name} KPI {rpt_attr_num}"
        })
        new_relationships.append({
            'type': 'ELEMENT_OF',
            'from': rpt_attr_id,
            'to': rpt_id
        })

    # Process
    proc_id = get_id(f"{domain_key}-proc")
    new_assets['Process'].append({
        'id': proc_id,
        'name': f"{domain_key}_workflow",
        'description': f"{domain_name} workflow process"
    })

# Merge new data into base data
for node_type, items in new_assets.items():
    if items:  # Only add if we have new items
        if node_type in base_data['assets']:
            base_data['assets'][node_type].extend(items)
        else:
            base_data['assets'][node_type] = items

# Add new relationships
base_data['relationships'].extend(new_relationships)

# Count final nodes
final_count = count_nodes(base_data)
print(f"\n✅ Final node count: {final_count}")

# Write out the expanded data
with open('metamodel/entities-large-1000.yaml', 'w') as f:
    yaml.dump(base_data, f, default_flow_style=False, sort_keys=False, width=120)

print(f"✅ Generated entities-large-1000.yaml with {final_count} nodes")
print(f"✅ Total relationships: {len(base_data['relationships'])}")
