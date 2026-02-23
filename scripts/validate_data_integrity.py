#!/usr/bin/env python3
"""
Validate data integrity constraints for the lineage metamodel.

Rules enforced:
1. Each dataset/model_version can have AT MOST one DATASET_PRODUCED_BY edge
2. Multiple datasets can be consumed by a job (IS_CONSUMED_BY is many-to-one)
3. Source datasets (no producer) are allowed
"""

import yaml
import sys
from pathlib import Path


def validate_single_producer(data):
    """Ensure each output has at most one producer."""
    produced_by = {}
    violations = []

    for rel in data.get('relationships', []):
        if rel.get('type') == 'DATASET_PRODUCED_BY':
            output = rel.get('from')
            job = rel.get('to')

            if output in produced_by:
                violations.append({
                    'output': output,
                    'existing_job': produced_by[output],
                    'duplicate_job': job
                })
            else:
                produced_by[output] = job

    return violations, produced_by


def main():
    # Load entities file
    entities_file = Path(__file__).parent.parent / 'metamodel' / 'entities-large-1000.yaml'

    print(f"🔍 Validating: {entities_file}")
    print("=" * 60)

    with open(entities_file, 'r') as f:
        data = yaml.safe_load(f)

    # Validate single producer rule
    violations, produced_by = validate_single_producer(data)

    if violations:
        print(f"\n❌ VALIDATION FAILED: Found {len(violations)} outputs with multiple producers\n")
        for v in violations:
            print(f"  Output: {v['output']}")
            print(f"    - Job 1: {v['existing_job']}")
            print(f"    - Job 2: {v['duplicate_job']} (DUPLICATE)")
            print()
        return 1
    else:
        print(f"✅ Single producer constraint: PASSED")
        print(f"   {len(produced_by)} outputs, each with exactly one producer job")

    # Count source datasets (no producer)
    all_datasets = []
    all_model_versions = []

    for node_type, nodes in data.get('assets', {}).items():
        if node_type == 'Dataset':
            # Exclude special subtypes that shouldn't have producers
            all_datasets.extend([
                n['id'] for n in nodes
                if n.get('sub_type') not in ['resultset', 'process']
            ])
        elif node_type == 'ModelVersion':
            all_model_versions.extend([n['id'] for n in nodes])

    all_outputs = set(all_datasets + all_model_versions)
    outputs_with_producers = set(produced_by.keys())
    source_datasets = all_outputs - outputs_with_producers

    print(f"\n📊 Coverage:")
    print(f"   Total datasets: {len(all_datasets)}")
    print(f"   Total model versions: {len(all_model_versions)}")
    print(f"   Outputs with producers: {len(outputs_with_producers)}")
    print(f"   Source datasets (no producer): {len(source_datasets)}")

    if source_datasets:
        print(f"\n📌 Source datasets (intentionally have no producer):")
        for src in sorted(source_datasets)[:10]:
            print(f"   - {src}")
        if len(source_datasets) > 10:
            print(f"   ... and {len(source_datasets) - 10} more")

    print(f"\n✅ All validation checks passed!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
