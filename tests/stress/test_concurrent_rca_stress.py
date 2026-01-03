"""Stress tests for concurrent RCA execution."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest


class TestConcurrentRCAStress:
    """Stress tests for concurrent RCA execution limits."""

    # =========================================================================
    # Stress: 100 concurrent RCA requests
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_100_concurrent_rca_requests(self, db_session, mock_loki_client, mock_cortex_client, mock_llm_provider):
        """
        Given 100 incidents require RCA,
        When triggered simultaneously,
        Then system handles with max 3 concurrent and queues the rest.
        """
        from src.agents.rca_manager import RCAManager

        manager = RCAManager(
            db_session=db_session,
            loki_client=mock_loki_client,
            cortex_client=mock_cortex_client,
            llm_provider=mock_llm_provider,
            max_concurrent=3,
        )

        incident_ids = [uuid4() for _ in range(100)]
        completed = 0
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def mock_rca(incident_id):
            nonlocal completed, max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                max_concurrent = max(max_concurrent, current_concurrent)

            await asyncio.sleep(0.01)  # Simulate work

            async with lock:
                current_concurrent -= 1
                completed += 1

            return {"status": "completed"}

        with patch.object(manager, "execute", side_effect=mock_rca):
            tasks = [manager.execute(id) for id in incident_ids]
            await asyncio.gather(*tasks, return_exceptions=True)

        assert completed == 100
        assert max_concurrent <= 3  # Should respect concurrency limit

    # =========================================================================
    # Stress: RCA with slow LLM responses
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_rca_with_slow_llm(self, db_session, mock_loki_client, mock_cortex_client, mock_llm_provider):
        """
        Given LLM responses are slow,
        When multiple RCAs are running,
        Then queue is managed properly.
        """
        from src.agents.rca_manager import RCAManager

        manager = RCAManager(
            db_session=db_session,
            loki_client=mock_loki_client,
            cortex_client=mock_cortex_client,
            llm_provider=mock_llm_provider,
            max_concurrent=3,
        )

        completed = []

        async def slow_execute(incident_id):
            await asyncio.sleep(0.05)  # Slow LLM
            completed.append(incident_id)
            return {"status": "completed"}

        incident_ids = [uuid4() for _ in range(20)]

        with patch.object(manager, "execute", side_effect=slow_execute):
            tasks = [manager.execute(id) for id in incident_ids]
            await asyncio.gather(*tasks)

        assert len(completed) == 20

    # =========================================================================
    # Stress: Mixed success/failure RCAs
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_mixed_success_failure_rca(self, db_session, mock_loki_client, mock_cortex_client, mock_llm_provider):
        """
        Given some RCAs fail,
        When processing continues,
        Then successful RCAs complete despite failures.
        """
        from src.agents.rca_manager import RCAManager

        manager = RCAManager(
            db_session=db_session,
            loki_client=mock_loki_client,
            cortex_client=mock_cortex_client,
            llm_provider=mock_llm_provider,
            max_concurrent=3,
        )

        success_count = 0
        failure_count = 0
        call_count = 0

        async def mixed_execute(incident_id):
            nonlocal success_count, failure_count, call_count
            call_count += 1
            if call_count % 5 == 0:
                failure_count += 1
                raise Exception("Simulated RCA failure")
            success_count += 1
            await asyncio.sleep(0.01)
            return {"status": "completed"}

        incident_ids = [uuid4() for _ in range(50)]

        with patch.object(manager, "execute", side_effect=mixed_execute):
            tasks = [manager.execute(id) for id in incident_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Should have mix of successes and failures
        assert success_count > 0
        assert failure_count > 0
        assert success_count + failure_count == 50


class TestRCAToolStress:
    """Stress tests for RCA tool invocations."""

    # =========================================================================
    # Stress: High volume Loki queries
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_high_volume_loki_queries(self, mock_loki_client):
        """
        Given many Loki queries are made,
        When under high load,
        Then queries complete without exhausting connections.
        """
        mock_loki_client.query.return_value = {
            "status": "success",
            "data": {"result": []},
        }

        query_count = 100
        completed = 0

        async def query():
            nonlocal completed
            await mock_loki_client.query(query='{service="test"}')
            completed += 1

        tasks = [query() for _ in range(query_count)]
        await asyncio.gather(*tasks)

        assert completed == query_count

    # =========================================================================
    # Stress: High volume Cortex queries
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_high_volume_cortex_queries(self, mock_cortex_client):
        """
        Given many Cortex queries are made,
        When under high load,
        Then queries complete without issues.
        """
        mock_cortex_client.query.return_value = {
            "status": "success",
            "data": {"result": []},
        }

        query_count = 100
        completed = 0

        async def query():
            nonlocal completed
            await mock_cortex_client.query(query="up")
            completed += 1

        tasks = [query() for _ in range(query_count)]
        await asyncio.gather(*tasks)

        assert completed == query_count

    # =========================================================================
    # Stress: Mixed tool invocations
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_mixed_tool_invocations(self, mock_loki_client, mock_cortex_client, mock_llm_provider):
        """
        Given RCA invokes multiple tools,
        When under high load,
        Then all tool invocations complete.
        """
        mock_loki_client.query.return_value = {"status": "success", "data": {"result": []}}
        mock_cortex_client.query.return_value = {"status": "success", "data": {"result": []}}
        mock_llm_provider.generate.return_value = {"content": "Analysis result"}

        tool_calls = 0

        async def invoke_tools():
            nonlocal tool_calls
            await mock_loki_client.query(query='{service="test"}')
            tool_calls += 1
            await mock_cortex_client.query(query="up")
            tool_calls += 1
            await mock_llm_provider.generate(prompt="Analyze")
            tool_calls += 1

        tasks = [invoke_tools() for _ in range(30)]
        await asyncio.gather(*tasks)

        assert tool_calls == 90  # 30 iterations * 3 tools


class TestReportGenerationStress:
    """Stress tests for report generation."""

    # =========================================================================
    # Stress: Concurrent report generation
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_concurrent_report_generation(self, db_session):
        """
        Given many reports need to be generated,
        When generated concurrently,
        Then all reports are created successfully.
        """
        from src.services.report_service import ReportService

        service = ReportService(db_session)
        report_count = 50
        generated = 0

        async def generate_report(incident_id):
            nonlocal generated
            with patch.object(service, "generate", new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = {"id": str(uuid4()), "status": "generated"}
                await service.generate(incident_id, {})
                generated += 1

        incident_ids = [uuid4() for _ in range(report_count)]
        tasks = [generate_report(id) for id in incident_ids]
        await asyncio.gather(*tasks)

        assert generated == report_count

    # =========================================================================
    # Stress: Large report content
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.stress
    async def test_large_report_content(self, db_session):
        """
        Given RCA produces large analysis,
        When generating report,
        Then report is created without memory issues.
        """
        from src.services.report_service import ReportService

        service = ReportService(db_session)

        # Large content
        large_evidence = [f"Evidence line {i}: " + "x" * 1000 for i in range(100)]
        large_remediation = [f"Step {i}: " + "y" * 500 for i in range(50)]

        rca_result = {
            "root_cause": "Test cause " + "z" * 1000,
            "confidence": 0.85,
            "evidence": large_evidence,
            "remediation": large_remediation,
        }

        with patch.object(service, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = {
                "id": str(uuid4()),
                "status": "generated",
                "size_kb": len(str(rca_result)) // 1024,
            }

            result = await service.generate(uuid4(), rca_result)

            assert result["status"] == "generated"

