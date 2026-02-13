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

    def test_y_02_no_sibling_traversal(self, traversal_engine, verify_graph_loaded):
        """
        Test Y-02: Y-axis should NOT traverse to siblings

        When traversing from Agentic System up to Use Case (parent), then back down,
        we should NOT see Model which is also a child of the same Use Case.

        Scenario:
        - Start: Agentic System (asys-001)
        - Y-up: Use Case (uc-001) ✅ ALLOWED (parent)
        - From Use Case, Y-down to Model (model-001) ❌ BLOCKED (sibling of asys-001)

        The fix prevents reversing Y-direction:
        - Once you go UP from base, you can only continue UP (not down to siblings)
        - Once you go DOWN from base, you can only continue DOWN (not up to siblings)
        """
        result = traversal_engine.traverse(
            start_node_id="asys-001",  # fraud_review_system (AgenticSystem)
            axes=["y"],
            y_direction="both",
            max_depth=10
        )

        visited_node_ids = {node['id'] for node in result.nodes}

        print(f"\nY-axis both directions from agentic system:")
        print(f"Visited nodes: {visited_node_ids}")

        # Should reach use_case going UP
        assert "uc-001" in visited_node_ids, "Should reach use_case (parent)"

        # Should reach agentic_system_version going DOWN
        assert "asysv-001" in visited_node_ids, "Should reach agentic_system_version (child)"

        # Should NOT reach model-001 (sibling - different hierarchy)
        # model-001 is also connected to uc-001 via MODEL_USE_CASE, but it's a sibling
        assert "model-001" not in visited_node_ids, (
            "Should NOT reach model-001 (sibling of agentic_system via use_case). "
            "This indicates Y-axis direction reversal is incorrectly allowed."
        )

        print(f"\n✓ Y-02 PASSED: Siblings correctly blocked")
        print(f"✓ Can traverse up to parent (use_case)")
        print(f"✓ Can traverse down to children (agentic_system_version)")
        print(f"✓ Cannot traverse to siblings (model)")

    def test_z_02_z_blocked_after_upstream(self, traversal_engine, verify_graph_loaded):
        """
        Test Z-02: Z-axis should be BLOCKED after going upstream

        Z-axis relationships should only be available from the input node and its
        children (downstream nodes). When we traverse upstream to parent nodes,
        their Z-axis relationships should not be available because they may open
        up directions that are not relevant to the chosen node.

        Scenario:
        - Start: fraud_predictions (ds-004)
        - X-upstream: curated_transactions (ds-002) ✅ ALLOWED
        - From ds-002, Z-axis to workspace (ws-001) ❌ BLOCKED (parent's Z-relationships)

        The fix:
        - Z-axis available at input node: YES
        - Z-axis available after downstream: YES
        - Z-axis available after upstream: NO (this test)
        """
        # Start from fraud_predictions and traverse upstream
        result = traversal_engine.traverse(
            start_node_id="ds-004",  # fraud_predictions
            axes=["x", "z"],  # Enable both X and Z axes
            x_direction="upstream",  # Go upstream
            max_z_hops=1,
            max_depth=10
        )

        visited_node_ids = {node['id'] for node in result.nodes}

        print(f"\nVisited nodes from fraud_predictions (upstream + Z): {visited_node_ids}")

        # Should reach curated_transactions via upstream
        assert "ds-002" in visited_node_ids, "Should reach curated_transactions via upstream"

        # Should reach raw_transactions via upstream
        assert "ds-001" in visited_node_ids, "Should reach raw_transactions via upstream"

        # Check paths to see if any Z-axis hops occurred after upstream
        upstream_then_z_violation = False
        for path in result.paths:
            # Look for patterns where we go upstream, then take a Z-hop
            path_nodes = path['path']
            path_edges = path['edges']

            # Check if this path has both X-upstream and Z-axis edges
            has_upstream = False
            z_after_upstream = False

            for i, edge_info in enumerate(path_edges):
                axis = edge_info['axis']

                # Track if we've seen an upstream edge
                if axis == 'x':
                    # Check if it's upstream by looking at semantic direction
                    # For simplicity, if we're going from ds-004 backwards, it's upstream
                    if i == 0 or has_upstream:
                        has_upstream = True

                # If we see Z-axis after upstream, that's a violation
                if axis == 'z' and has_upstream:
                    z_after_upstream = True
                    print(f"\nVIOLATION: Z-axis hop after upstream in path: {' → '.join(path_nodes)}")
                    for j, e in enumerate(path_edges):
                        print(f"  Edge {j}: {e['axis']} - {e['edge']['type']}")
                    upstream_then_z_violation = True

        assert not upstream_then_z_violation, (
            "Z-axis hops should be BLOCKED after going upstream. "
            "Parent node Z-relationships may not be relevant to the chosen node."
        )

        # Additionally, workspace should NOT be reachable via this upstream+Z traversal
        # ws-001 is a Z-axis neighbor of ds-002 (curated_transactions)
        # But since we reached ds-002 via upstream, its Z-axis should be blocked
        assert "ws-001" not in visited_node_ids, (
            "Should NOT reach workspace (ws-001) - it's a Z-axis neighbor of "
            "curated_transactions, but we reached curated_transactions via upstream, "
            "so its Z-axis relationships should be blocked"
        )

        # use_case should also not be reachable
        assert "uc-001" not in visited_node_ids, (
            "Should NOT reach use_case (uc-001) - it's a Z-axis neighbor of "
            "curated_transactions, but Z-axis should be blocked after upstream traversal"
        )

        print(f"\n✓ Z-02 PASSED: Z-axis correctly blocked after upstream traversal")
        print(f"✓ Can traverse upstream via X-axis")
        print(f"✓ Cannot take Z-axis hops from parent nodes reached via upstream")

    def test_z_03_z_blocked_after_y_up_to_parent(self, traversal_engine, verify_graph_loaded):
        """
        Test Z-03: Z-axis should be BLOCKED after going "up" on Y-axis to parent nodes

        Z-axis relationships should only be available from the input node and its
        descendants (children going "down"). When we traverse "up" to parent nodes,
        their Z-axis relationships should not be available because they may open
        up directions that are not relevant to the chosen node.

        Scenario:
        - Start: agentic_system (asys-001)
        - Y-up: use_case (uc-001) ✅ ALLOWED (parent)
        - From uc-001, Z-axis to workspace (ws-001) ❌ BLOCKED (parent's Z-relationships)
        - From uc-001, Z-axis to datasets (ds-002, ds-003) ❌ BLOCKED (parent's Z-relationships)

        BUT Z-axis should still work from descendants:
        - Y-down: agentic_system_version (asysv-001) ✅ ALLOWED (child)
        - Y-down: agent_version (agv-001) ✅ ALLOWED (grandchild)
        - From agv-001, Z-axis to datasets (ds-004, ds-006) via USES ✅ ALLOWED (descendant's Z)

        The fix:
        - Z-axis available at input node: YES
        - Z-axis available after Y-down (to children): YES
        - Z-axis available after Y-up (to parents): NO (this test)
        """
        # Start from agentic_system and traverse with Y and Z axes
        result = traversal_engine.traverse(
            start_node_id='asys-001',  # fraud_review_system
            axes=['y', 'z'],
            y_direction='both',
            max_z_hops=1,
            max_depth=10
        )

        visited_node_ids = {node['id'] for node in result.nodes}

        print(f"\nVisited nodes from agentic_system (Y+Z): {visited_node_ids}")

        # Should reach use_case (parent) via Y-up
        assert 'uc-001' in visited_node_ids, "Should reach use_case (parent) via Y-up"

        # Should reach descendants via Y-down
        assert 'asysv-001' in visited_node_ids, "Should reach agentic_system_version (child)"
        assert 'agv-001' in visited_node_ids, "Should reach agent_version (grandchild)"

        # Should NOT reach parent's Z-axis neighbors
        # use_case (uc-001) has Z-axis relationships to workspace and datasets
        assert 'ws-001' not in visited_node_ids, (
            "Should NOT reach workspace (ws-001) - it's a Z-axis neighbor of "
            "use_case (parent), so should be blocked"
        )
        assert 'ds-002' not in visited_node_ids, (
            "Should NOT reach curated_transactions (ds-002) - it's a Z-axis neighbor of "
            "use_case (parent), so should be blocked"
        )
        assert 'ds-003' not in visited_node_ids, (
            "Should NOT reach feature_set (ds-003) - it's a Z-axis neighbor of "
            "use_case (parent), so should be blocked"
        )

        # SHOULD reach descendant's Z-axis neighbors
        # agent_version (agv-001) has USES relationships to datasets
        # These are Z-axis from a descendant, so should be allowed
        z_from_descendants = {'ds-004', 'ds-006', 'mv-003', 'mcpt-001'}
        found_z_from_descendants = visited_node_ids & z_from_descendants
        assert len(found_z_from_descendants) > 0, (
            "Should reach some Z-axis neighbors from descendants (agent_version's USES relationships)"
        )

        # Verify no Y-up then Z-axis paths exist
        y_up_then_z_violation = False
        for path in result.paths:
            path_edges = path['edges']
            has_y_up = False
            z_after_y_up = False

            for i, edge_info in enumerate(path_edges):
                axis = edge_info['axis']

                # Track if we've seen a Y-up edge
                if axis == 'y':
                    # Check the neighbor_info to see if it's "up"
                    # For simplicity, we'll check if we're at use_case after a Y edge
                    if i < len(path['path']) - 1 and path['path'][i+1] == 'uc-001':
                        has_y_up = True

                # If we see Z-axis after Y-up, that's a violation
                if axis == 'z' and has_y_up:
                    z_after_y_up = True
                    print(f"\nVIOLATION: Z-axis hop after Y-up in path: {' → '.join(path['path'])}")
                    y_up_then_z_violation = True

        assert not y_up_then_z_violation, (
            "Z-axis hops should be BLOCKED after going 'up' to parent nodes. "
            "Parent node Z-relationships may not be relevant to the chosen node."
        )

        print(f"\n✓ Z-03 PASSED: Z-axis correctly blocked after Y-up to parent nodes")
        print(f"✓ Can traverse 'up' to parent (use_case)")
        print(f"✓ Cannot take Z-axis hops from parent nodes")
        print(f"✓ CAN take Z-axis hops from descendants (agent_version)")


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
            if node['type'] == 'job'
        ]
        assert len(transformer_nodes) > 0, "Should include jobs as transformers"


class TestOneHopAPI:
    """Tests for the 1-hop API"""

    def test_one_hop_all_axes(self, traversal_engine, verify_graph_loaded):
        """
        Test 1-hop API from curated_transactions with all axes enabled.

        Expected neighbors:
        - X-axis upstream: raw_transactions (via job-001)
        - X-axis downstream: fraud_feature_set (via job-002)
        - Y-axis: attributes (attr-001, attr-002, attr-003)
        - Z-axis: workspace, use_case
        """
        result = traversal_engine.one_hop(
            start_node_id="ds-002",  # curated_transactions
            axes=["x", "y", "z"]
        )

        # Verify start node
        assert result.start_node['id'] == "ds-002"
        assert result.start_node['name'] == "curated_transactions"

        # Check X-axis neighbors
        print(f"\nX-axis upstream: {len(result.x_axis['upstream'])} nodes")
        print(f"X-axis downstream: {len(result.x_axis['downstream'])} nodes")

        # Should have upstream and downstream neighbors
        assert len(result.x_axis['upstream']) > 0, "Should have upstream neighbors"
        assert len(result.x_axis['downstream']) > 0, "Should have downstream neighbors"

        # Check Y-axis neighbors (attributes)
        print(f"Y-axis up: {len(result.y_axis['up'])} nodes")
        print(f"Y-axis down: {len(result.y_axis['down'])} nodes")

        # Attributes should be "down" from dataset (dataset is parent)
        # Actually, based on the taxonomy, IS_ATTRIBUTE_FOR goes from attribute to dataset
        # with semantic_up: forward, so going from dataset we go "down" to attributes
        y_all = result.y_axis['up'] + result.y_axis['down']
        assert len(y_all) > 0, "Should have Y-axis neighbors"

        # Check Z-axis neighbors
        print(f"Z-axis: {len(result.z_axis)} nodes")
        z_node_ids = {n['node']['id'] for n in result.z_axis}

        # Should include workspace and use_case
        assert "ws-001" in z_node_ids or "uc-001" in z_node_ids, (
            "Should have Z-axis associations (workspace or use_case)"
        )

        print(f"\n✓ 1-hop API returned neighbors on all axes")

    def test_one_hop_z_axis_only(self, traversal_engine, verify_graph_loaded):
        """
        Test 1-hop API with only Z-axis enabled.

        This verifies that Z-axis neighbors are correctly identified
        from the base node.
        """
        result = traversal_engine.one_hop(
            start_node_id="ds-002",  # curated_transactions
            axes=["z"]
        )

        # Should have Z-axis neighbors
        assert len(result.z_axis) > 0, "Should have Z-axis neighbors"

        # X and Y should be empty
        assert len(result.x_axis['upstream']) == 0, "X-axis should be empty"
        assert len(result.x_axis['downstream']) == 0, "X-axis should be empty"
        assert len(result.y_axis['up']) == 0, "Y-axis should be empty"
        assert len(result.y_axis['down']) == 0, "Y-axis should be empty"

        z_node_ids = {n['node']['id'] for n in result.z_axis}
        print(f"\nZ-axis only: {z_node_ids}")

        print(f"✓ Z-axis only mode works correctly")

    def test_one_hop_from_agent_version(self, traversal_engine, verify_graph_loaded):
        """
        Test 1-hop API from agent_version.

        Expected:
        - Y-axis up: agentic_system_version
        - Z-axis: datasets, mcp_tool, model_version (via USES edges)
        """
        result = traversal_engine.one_hop(
            start_node_id="agv-001",  # fraud_reviewer_agent_v1
            axes=["x", "y", "z"]
        )

        # Y-axis: should go up to agentic_system_version
        y_up_ids = {n['node']['id'] for n in result.y_axis['up']}
        assert "asysv-001" in y_up_ids, "Should connect up to agentic_system_version"

        # Z-axis: should have USES relationships
        assert len(result.z_axis) > 0, "Should have Z-axis associations via USES"

        z_node_ids = {n['node']['id'] for n in result.z_axis}
        print(f"\nZ-axis from agent_version: {z_node_ids}")

        # Should include some of: ds-004, ds-006, mcpt-001, mv-003
        z_expected = {"ds-004", "ds-006", "mcpt-001", "mv-003"}
        assert len(z_node_ids & z_expected) > 0, (
            f"Should have Z-axis neighbors from USES edges, expected some of {z_expected}"
        )

        print(f"✓ 1-hop from agent_version includes Y-up and Z associations")

    def test_one_hop_metadata(self, traversal_engine, verify_graph_loaded):
        """Verify that metadata in 1-hop result is correct"""
        result = traversal_engine.one_hop(
            start_node_id="ds-002",
            axes=["x", "y", "z"]
        )

        # Check metadata counts match actual results
        assert result.metadata['total_x_upstream'] == len(result.x_axis['upstream'])
        assert result.metadata['total_x_downstream'] == len(result.x_axis['downstream'])
        assert result.metadata['total_y_up'] == len(result.y_axis['up'])
        assert result.metadata['total_y_down'] == len(result.y_axis['down'])
        assert result.metadata['total_z'] == len(result.z_axis)

        print(f"\n✓ Metadata counts are accurate")
        print(f"  X upstream: {result.metadata['total_x_upstream']}")
        print(f"  X downstream: {result.metadata['total_x_downstream']}")
        print(f"  Y up: {result.metadata['total_y_up']}")
        print(f"  Y down: {result.metadata['total_y_down']}")
        print(f"  Z: {result.metadata['total_z']}")
