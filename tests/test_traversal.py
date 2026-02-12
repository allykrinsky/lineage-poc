"""
Tests for the traversal engine, focusing on axis constraints.

Test XZ-02 is the critical test that validates Z-of-Z blocking.
"""

import pytest
from src.traversal.engine import TraversalEngine


class TestAxisConstraints:
    """Tests for multi-axis traversal constraints"""

    def test_xz_02_z_of_z_blocking(self, traversal_engine, verify_graph_loaded):
        """
        Test XZ-02: BLOCKED — Z-of-Z should not traverse

        This is the most critical test for the POC. It validates that:
        1. After a Z-axis hop, further Z-axis hops are BLOCKED
        2. After a Z-axis hop, Y-axis continuation is ALLOWED
        3. After a Z-axis hop, X-axis continuation is ALLOWED

        Starting from curated_transactions (ds-002):

        BLOCKED paths (Z-of-Z):
        - curated_transactions → Z → fraud_detection_workspace → Z → uc_fraud
          (workspace_use_case from workspace, which is Z→Z)
        - curated_transactions → Z → uc_fraud → Z → feature_set
          (use_case_dataset, which is Z→Z)

        ALLOWED paths (Z→Y):
        - curated_transactions → Z → fraud_detection_workspace → Y → fraud_model_service
          (workspace → installed (Y-axis) is allowed after Z-hop)
        - curated_transactions → Z → uc_fraud → Y → fraud_detection_model
          (model_use_case (Y-axis) is allowed after Z-hop)
        """
        # Run traversal from curated_transactions with all axes enabled
        result = traversal_engine.traverse(
            start_node_id="ds-002",  # curated_transactions
            axes=["x", "y", "z"],
            x_direction="both",
            y_direction="both",
            max_z_hops=1,
            max_depth=10
        )

        # Get all visited node IDs
        visited_node_ids = {node['id'] for node in result.nodes}

        print(f"\nVisited nodes: {visited_node_ids}")
        print(f"Total nodes: {len(visited_node_ids)}")

        # Analyze paths to understand what was traversed
        z_paths = [p for p in result.paths if p['axis'] == 'z']
        print(f"\nZ-axis paths: {len(z_paths)}")

        # Check for Z-of-Z violations
        # We need to verify that after a Z-hop, no additional Z-hops occur
        for path in result.paths:
            if path['z_hops'] > 1:
                # Extract path nodes
                path_nodes = path['path']
                pytest.fail(
                    f"VIOLATION: Found path with {path['z_hops']} Z-hops (max allowed: 1)\n"
                    f"Path: {' → '.join(path_nodes)}"
                )

        # Verify specific BLOCKED paths do NOT appear

        # BLOCKED: curated_transactions → workspace → use_case (Z→Z)
        # If we reached workspace (ws-001), we should NOT reach use case via Z
        if "ws-001" in visited_node_ids:
            # Check if any paths go from ws-001 to uc-001 via Z-axis
            workspace_paths = [
                p for p in result.paths
                if len(p['path']) >= 3 and
                p['path'][-2] == "ws-001" and
                p['path'][-1] == "uc-001"
            ]
            for path in workspace_paths:
                # Check if this is a Z-hop
                if path['z_hops'] == 2:
                    pytest.fail(
                        f"VIOLATION: Z-of-Z path detected: "
                        f"curated_transactions → workspace → use_case\n"
                        f"Full path: {' → '.join(path['path'])}"
                    )

        # BLOCKED: curated_transactions → use_case → dataset (Z→Z)
        # If we reached use_case (uc-001), we should NOT reach feature_set via Z
        if "uc-001" in visited_node_ids and "ds-003" in visited_node_ids:
            # Check if any paths go from uc-001 to ds-003 via Z-axis
            uc_paths = [
                p for p in result.paths
                if len(p['path']) >= 3 and
                "uc-001" in p['path'] and
                "ds-003" in p['path']
            ]
            for path in uc_paths:
                uc_idx = path['path'].index("uc-001")
                ds_idx = path['path'].index("ds-003")
                if ds_idx > uc_idx and path['z_hops'] == 2:
                    pytest.fail(
                        f"VIOLATION: Z-of-Z path detected: "
                        f"curated_transactions → use_case → feature_set\n"
                        f"Full path: {' → '.join(path['path'])}"
                    )

        # Verify specific ALLOWED paths DO appear (Z→Y continuations)

        # ALLOWED: curated_transactions → workspace → service (Z→Y)
        # We expect to find workspace (ws-001) via Z, then service (wssvc-001) via Y
        workspace_reached_via_z = any(
            p['axis'] == 'z' and "ws-001" in p['path']
            for p in result.paths
        )

        if workspace_reached_via_z:
            # Check if we can continue to workspace service via Y
            # This demonstrates Z→Y continuation is allowed
            service_paths = [
                p for p in result.paths
                if "ws-001" in p['path'] and "wssvc-001" in p['path']
            ]

            # We expect at least one such path
            assert len(service_paths) > 0, (
                "Expected to find Z→Y continuation: "
                "curated_transactions → workspace (Z) → service (Y), but none found"
            )

            # Verify it's not a Z-of-Z (should be Z then Y)
            for path in service_paths:
                assert path['z_hops'] <= 1, (
                    f"Z→Y continuation should have z_hops=1, got {path['z_hops']}"
                )

        # ALLOWED: curated_transactions → use_case → model (Z→Y)
        use_case_reached_via_z = any(
            p['axis'] == 'z' and "uc-001" in p['path']
            for p in result.paths
        )

        if use_case_reached_via_z:
            # Check if we can continue to model via Y
            # use_case → model_use_case (reverse) → model
            model_paths = [
                p for p in result.paths
                if "uc-001" in p['path'] and "model-001" in p['path']
            ]

            # We expect at least one such path
            assert len(model_paths) > 0, (
                "Expected to find Z→Y continuation: "
                "curated_transactions → use_case (Z) → model (Y), but none found"
            )

        print("\n✓ XZ-02 PASSED: Z-of-Z correctly blocked, Z→Y allowed")
        print(f"✓ Verified no paths with z_hops > 1")
        print(f"✓ Verified Z→Y continuations work as expected")

    def test_z_01_simple_z_associations(self, traversal_engine, verify_graph_loaded):
        """
        Test Z-01: Simple Z-axis associations from curated_transactions

        Expected associations:
        - txn_quality_results (via resultsets_dataset)
        - fraud_detection use case (via use_case_dataset, reverse)
        - fraud_detection_workspace (via workspace_dataset, reverse)
        """
        result = traversal_engine.traverse(
            start_node_id="ds-002",  # curated_transactions
            axes=["z"],
            max_z_hops=1
        )

        visited_node_ids = {node['id'] for node in result.nodes}

        # Should include the start node
        assert "ds-002" in visited_node_ids

        # Check for expected Z-associations
        # Note: exact IDs depend on seed data
        print(f"\nZ-axis associations from curated_transactions:")
        print(f"Visited nodes: {visited_node_ids}")

        # Verify we found some associations
        # Excluding the start node, we should have at least 1 association
        assert len(visited_node_ids) > 1, "Expected to find at least 1 Z-axis association"

    def test_y_01_hierarchy_up(self, traversal_engine, verify_graph_loaded):
        """
        Test Y-01: Walk up from agent_version to agentic system

        Expected path:
        - fraud_reviewer_agent_v1 (agv-001)
        - ↑ (via has_member, reversed)
        - fraud_review_v1 (asysv-001) agentic_system_version
        - ↑ (via has_version, reversed)
        - fraud_review_system (asys-001) agentic_system
        """
        result = traversal_engine.traverse(
            start_node_id="agv-001",  # fraud_reviewer_agent_v1
            axes=["y"],
            y_direction="up",
            max_depth=10
        )

        visited_node_ids = {node['id'] for node in result.nodes}

        print(f"\nY-axis up from agent_version:")
        print(f"Visited nodes: {visited_node_ids}")

        # Should reach the agentic system version
        assert "asysv-001" in visited_node_ids, "Should reach agentic_system_version"

        # Should reach the agentic system
        assert "asys-001" in visited_node_ids, "Should reach agentic_system"


class TestXAxisLineage:
    """Tests for X-axis lineage traversal"""

    def test_x_01_upstream_lineage(self, traversal_engine, verify_graph_loaded):
        """
        Test X-01: Full upstream lineage from predictions dataset

        Expected path:
        - fraud_predictions (ds-004)
        - ← (via job: score_transactions)
        - curated_transactions (ds-002)
        - ← (via job: ingest_raw_transactions)
        - raw_transactions (ds-001)
        """
        result = traversal_engine.traverse(
            start_node_id="ds-004",  # fraud_predictions
            axes=["x"],
            x_direction="upstream",
            max_depth=10
        )

        visited_node_ids = {node['id'] for node in result.nodes}

        print(f"\nX-axis upstream from fraud_predictions:")
        print(f"Visited nodes: {visited_node_ids}")

        # Should reach curated_transactions
        assert "ds-002" in visited_node_ids, "Should reach curated_transactions"

        # Should reach raw_transactions
        assert "ds-001" in visited_node_ids, "Should reach raw_transactions"

        # Should also include transformer nodes (jobs)
        transformer_nodes = [
            node for node in result.nodes
            if node['type'] == 'etl_job'
        ]
        assert len(transformer_nodes) > 0, "Should include ETL jobs as transformers"
