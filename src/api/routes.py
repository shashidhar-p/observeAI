"""FastAPI routes for the RCA system."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    AlertListResponse,
    AlertManagerWebhookPayload,
    AlertResponse,
    HealthResponse,
    IncidentListResponse,
    IncidentResponse,
    IncidentSummary,
    ManualCorrelationRequest,
    ManualCorrelationResponse,
    RCAReportListResponse,
    RCAReportResponse,
    RCAReportSummary,
    ReadinessCheck,
    ReadinessResponse,
    WebhookAcceptedResponse,
)
from src.api.schemas import (
    AlertSeverity as SchemaSeverity,
)
from src.api.schemas import (
    AlertStatus as SchemaStatus,
)
from src.api.schemas import (
    IncidentStatus as SchemaIncidentStatus,
)
from src.config import get_settings
from src.database import get_session

logger = logging.getLogger(__name__)
settings = get_settings()

# Track server start time for uptime calculation
SERVER_START_TIME = time.time()

# Create routers
health_router = APIRouter(tags=["health"])
api_router = APIRouter(prefix="/api/v1", tags=["api"])
webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ============================================================================
# Health Endpoints
# ============================================================================


@health_router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check endpoint."""
    from src import __version__

    uptime = int(time.time() - SERVER_START_TIME)
    return HealthResponse(
        status="healthy",
        version=__version__,
        uptime_seconds=uptime,
    )


@health_router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check() -> ReadinessResponse:
    """
    Readiness check endpoint.

    Verifies connectivity to all required services:
    - Database (PostgreSQL)
    - Loki
    - Cortex
    - LLM API (Anthropic)
    """
    checks = ReadinessCheck(
        database=await _check_database(),
        loki=await _check_loki(),
        cortex=await _check_cortex(),
        llm=await _check_llm(),
    )

    ready = all([checks.database, checks.loki, checks.cortex, checks.llm])

    response = ReadinessResponse(ready=ready, checks=checks)

    if not ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response.model_dump(),
        )

    return response


async def _check_database() -> bool:
    """Check database connectivity."""
    try:
        from sqlalchemy import text

        from src.database import async_session_factory

        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _check_loki() -> bool:
    """Check Loki connectivity."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.loki_url}/ready")
            return response.status_code == 200
    except Exception:
        return False


async def _check_cortex() -> bool:
    """Check Cortex connectivity."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.cortex_url}/ready")
            return response.status_code == 200
    except Exception:
        return False


async def _check_llm() -> bool:
    """Check LLM API availability."""
    # For now, just check that the API key is configured
    # A full check would make an API call, but that costs tokens
    return bool(settings.anthropic_api_key)


# ============================================================================
# Webhook Endpoints
# ============================================================================


@webhook_router.post("/alertmanager", response_model=WebhookAcceptedResponse, status_code=202)
async def receive_alertmanager_webhook(
    payload: AlertManagerWebhookPayload,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> WebhookAcceptedResponse:
    """
    Receive alerts from Alert Manager.

    This endpoint acknowledges receipt immediately (within 2 seconds)
    and processes alerts asynchronously.
    """
    from src.services.llm.factory import create_llm_provider
    from src.services.webhook import WebhookService

    try:
        # Create LLM provider for semantic correlation
        llm_provider = None
        try:
            llm_provider = create_llm_provider(settings)
        except Exception as e:
            logger.warning(f"LLM provider not available for semantic correlation: {e}")

        webhook_service = WebhookService(session, llm_provider=llm_provider)
        alert_ids, incident_ids = await webhook_service.process_webhook(payload)

        # Commit the transaction before background tasks run
        await session.commit()

        # Queue background RCA processing for each incident
        for incident_id in incident_ids:
            background_tasks.add_task(run_rca_for_incident, incident_id)

        return WebhookAcceptedResponse(
            status="accepted",
            message="Alert received and queued for processing",
            alerts_received=len(payload.alerts),
            processing_ids=alert_ids,
        )

    except Exception as e:
        logger.exception(f"Webhook processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


async def run_rca_for_incident(incident_id: UUID) -> None:
    """
    Background task to run RCA analysis for an incident.

    Args:
        incident_id: ID of the incident to analyze
    """
    import asyncio

    from src.database import get_session_context
    from src.models import IncidentStatus
    from src.services.incident_service import IncidentService
    from src.services.rca_agent import RCAAgent
    from src.services.report_service import ReportService

    # Wait for the main request's session to commit
    await asyncio.sleep(1)

    logger.info(f"Starting RCA analysis for incident {incident_id}")

    # First, transition to ANALYZING status in a separate transaction
    # This ensures the UI can see the ANALYZING state while RCA runs
    try:
        async with get_session_context() as session:
            incident_service = IncidentService(session)
            incident = await incident_service.get(incident_id)
            if not incident:
                logger.error(f"Incident {incident_id} not found")
                return

            # Only transition if still OPEN (not already being analyzed)
            if incident.status == IncidentStatus.OPEN:
                await incident_service.update_status(incident_id, IncidentStatus.ANALYZING)
                await session.commit()
                logger.info(f"Incident {incident_id} transitioned to ANALYZING")
            else:
                logger.info(f"Incident {incident_id} already in {incident.status.value} state, skipping")
                return
    except Exception as e:
        logger.error(f"Failed to transition incident {incident_id} to ANALYZING: {e}")
        return

    # Now run RCA in a new transaction
    try:
        async with get_session_context() as session:
            incident_service = IncidentService(session)
            report_service = ReportService(session)

            # Get incident with alerts
            incident = await incident_service.get_with_alerts(incident_id)
            if not incident:
                logger.error(f"Incident {incident_id} not found")
                return

            # Create pending report
            report = await report_service.create(incident_id=incident_id)

            # Run RCA agent
            agent = RCAAgent()

            if len(incident.alerts) == 1:
                result = await agent.analyze_alert(incident.alerts[0])
            else:
                result = await agent.analyze_incident(incident, list(incident.alerts))

            # Update report with results
            if result.get("success"):
                report_data = result["report"]
                await report_service.update_from_analysis(
                    report_id=report.id,
                    root_cause=report_data.get("root_cause", "Unknown"),
                    confidence_score=report_data.get("confidence_score", 0),
                    summary=report_data.get("summary", ""),
                    timeline=report_data.get("timeline", []),
                    evidence=report_data.get("evidence", {}),
                    remediation_steps=report_data.get("remediation_steps", []),
                    analysis_metadata=result.get("metadata"),
                )
                # Mark RCA as complete but don't auto-resolve - let ops resolve manually
                incident = await incident_service.get(incident_id)
                if incident:
                    from datetime import UTC
                    incident.rca_completed_at = datetime.now(UTC)
                    incident.status = IncidentStatus.OPEN
                    await session.flush()
                logger.info(f"RCA complete for incident {incident_id}")
            else:
                await report_service.mark_failed(
                    report_id=report.id,
                    error_message=result.get("error", "Unknown error"),
                    analysis_metadata=result.get("metadata"),
                )
                # Transition incident back to OPEN on RCA failure
                await incident_service.update_status(
                    incident_id, IncidentStatus.OPEN, validate_transition=True
                )
                logger.error(f"RCA failed for incident {incident_id}: {result.get('error')}")

    except Exception as e:
        logger.exception(f"RCA processing failed for incident {incident_id}: {e}")
        # Try to reset incident status on exception
        try:
            from src.database import get_session_context as get_cleanup_session
            async with get_cleanup_session() as cleanup_session:
                cleanup_service = IncidentService(cleanup_session)
                await cleanup_service.update_status(
                    incident_id, IncidentStatus.OPEN, validate_transition=True
                )
                await cleanup_session.commit()
        except Exception as cleanup_error:
            logger.error(f"Failed to reset incident {incident_id} status: {cleanup_error}")


# ============================================================================
# API Endpoints for Incidents
# ============================================================================


@api_router.post(
    "/admin/incidents/reset-stuck",
    summary="Reset stuck analyzing incidents",
    tags=["admin"],
)
async def reset_stuck_incidents(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Reset all incidents stuck in 'analyzing' status back to 'open'.

    This is an admin endpoint for cleaning up incidents that failed RCA
    without proper status transition.
    """
    from sqlalchemy import update

    from src.models import Incident, IncidentStatus

    result = await session.execute(
        update(Incident)
        .where(Incident.status == IncidentStatus.ANALYZING)
        .values(status=IncidentStatus.OPEN)
        .returning(Incident.id)
    )
    reset_ids = [str(row[0]) for row in result.fetchall()]
    await session.commit()

    logger.info(f"Reset {len(reset_ids)} stuck analyzing incidents to OPEN")
    return {
        "status": "success",
        "reset_count": len(reset_ids),
        "incident_ids": reset_ids,
    }


@api_router.post(
    "/incidents/{incident_id}/correlate",
    response_model=ManualCorrelationResponse,
    summary="Manually correlate alerts with an incident",
)
async def manual_correlate_alerts(
    incident_id: UUID,
    request: ManualCorrelationRequest,
    session: AsyncSession = Depends(get_session),
) -> ManualCorrelationResponse:
    """
    Manually correlate alerts with an existing incident.

    This allows operators to override automatic correlation by manually
    grouping alerts that the system didn't correlate automatically.
    """
    from src.services.incident_service import IncidentService

    incident_service = IncidentService(session)

    # Check incident exists
    incident = await incident_service.get(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found",
        )

    # Perform manual correlation
    updated = await incident_service.manual_correlate(incident_id, request.alert_ids)

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to correlate alerts",
        )

    return ManualCorrelationResponse(
        success=True,
        incident_id=incident_id,
        alerts_correlated=len(request.alert_ids),
        message=f"Successfully correlated {len(request.alert_ids)} alert(s) with incident",
    )


# ============================================================================
# Alert Endpoints (User Story 5)
# ============================================================================


@api_router.get("/alerts", response_model=AlertListResponse, summary="List alerts")
async def list_alerts(
    status: SchemaStatus | None = None,
    severity: SchemaSeverity | None = None,
    service: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> AlertListResponse:
    """
    List alerts with optional filtering.

    Query parameters:
    - status: Filter by alert status (firing, resolved)
    - severity: Filter by severity (critical, warning, info)
    - service: Filter by service label
    - since: Filter alerts starting after this time
    - until: Filter alerts starting before this time
    - limit: Maximum number of results (default: 50)
    - offset: Number of results to skip (default: 0)
    """
    from src.models import AlertSeverity, AlertStatus
    from src.services.alert_service import AlertService

    alert_service = AlertService(session)

    # Convert schema enums to model enums
    model_status = AlertStatus(status.value) if status else None
    model_severity = AlertSeverity(severity.value) if severity else None

    alerts, total = await alert_service.list_alerts(
        status=model_status,
        severity=model_severity,
        service=service,
        since=since,
        until=until,
        limit=min(limit, 100),  # Cap at 100
        offset=offset,
    )

    return AlertListResponse(
        alerts=[AlertResponse.model_validate(a) for a in alerts],
        total=total,
        limit=limit,
        offset=offset,
    )


@api_router.get("/alerts/{alert_id}", response_model=AlertResponse, summary="Get alert by ID")
async def get_alert(
    alert_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> AlertResponse:
    """Get a specific alert by ID."""
    from src.services.alert_service import AlertService

    alert_service = AlertService(session)
    alert = await alert_service.get(alert_id)

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )

    return AlertResponse.model_validate(alert)


# ============================================================================
# Incident Endpoints (User Story 5)
# ============================================================================


@api_router.get("/incidents", response_model=IncidentListResponse, summary="List incidents")
async def list_incidents(
    status: SchemaIncidentStatus | None = None,
    severity: SchemaSeverity | None = None,
    service: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> IncidentListResponse:
    """
    List incidents with optional filtering.

    Query parameters:
    - status: Filter by incident status (open, analyzing, resolved, closed)
    - severity: Filter by severity (critical, warning, info)
    - service: Filter by affected service
    - since: Filter incidents starting after this time
    - until: Filter incidents starting before this time
    - limit: Maximum number of results (default: 50)
    - offset: Number of results to skip (default: 0)
    """
    from src.models import IncidentSeverity, IncidentStatus
    from src.services.incident_service import IncidentService

    incident_service = IncidentService(session)

    # Convert schema enums to model enums
    model_status = IncidentStatus(status.value) if status else None
    model_severity = IncidentSeverity(severity.value) if severity else None

    incidents, total = await incident_service.list_incidents(
        status=model_status,
        severity=model_severity,
        service=service,
        since=since,
        until=until,
        limit=min(limit, 100),
        offset=offset,
    )

    return IncidentListResponse(
        incidents=[IncidentSummary.model_validate(i) for i in incidents],
        total=total,
        limit=limit,
        offset=offset,
    )


@api_router.get("/incidents/{incident_id}", response_model=IncidentResponse, summary="Get incident by ID")
async def get_incident(
    incident_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> IncidentResponse:
    """Get a specific incident by ID."""
    from src.services.incident_service import IncidentService

    incident_service = IncidentService(session)
    incident = await incident_service.get_with_alerts(incident_id)

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found",
        )

    return IncidentResponse.model_validate(incident)


@api_router.get(
    "/incidents/{incident_id}/alerts",
    response_model=list[AlertResponse],
    summary="Get alerts for incident",
)
async def get_incident_alerts(
    incident_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> list[AlertResponse]:
    """Get all alerts correlated with an incident."""
    from src.services.alert_service import AlertService
    from src.services.incident_service import IncidentService

    incident_service = IncidentService(session)
    incident = await incident_service.get(incident_id)

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found",
        )

    alert_service = AlertService(session)
    alerts = await alert_service.list_by_incident(incident_id)

    return [AlertResponse.model_validate(a) for a in alerts]


# ============================================================================
# Report Endpoints (User Story 5)
# ============================================================================


@api_router.get(
    "/incidents/{incident_id}/report",
    response_model=RCAReportResponse,
    summary="Get RCA report for incident",
)
async def get_incident_report(
    incident_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> RCAReportResponse:
    """Get the RCA report for a specific incident."""
    from src.services.report_service import ReportService

    report_service = ReportService(session)
    report = await report_service.get_by_incident(incident_id)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No RCA report found for incident {incident_id}",
        )

    return RCAReportResponse.model_validate(report)


@api_router.get("/reports", response_model=RCAReportListResponse, summary="List RCA reports")
async def list_reports(
    status: str | None = None,
    service: str | None = None,
    severity: SchemaSeverity | None = None,
    min_confidence: int | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> RCAReportListResponse:
    """
    List RCA reports with optional filtering.

    Query parameters:
    - status: Filter by report status (pending, complete, failed)
    - service: Filter by affected service
    - severity: Filter by severity
    - min_confidence: Minimum confidence score (0-100)
    - limit: Maximum number of results (default: 50)
    - offset: Number of results to skip (default: 0)
    """
    from src.models import RCAReportStatus
    from src.services.report_service import ReportService

    report_service = ReportService(session)

    # Convert status string to enum
    model_status = RCAReportStatus(status) if status else None

    reports, total = await report_service.list_reports(
        status=model_status,
        service=service,
        severity=severity.value if severity else None,
        min_confidence=min_confidence,
        limit=min(limit, 100),
        offset=offset,
    )

    return RCAReportListResponse(
        reports=[RCAReportSummary.model_validate(r) for r in reports],
        total=total,
        limit=limit,
        offset=offset,
    )


@api_router.get("/reports/{report_id}", response_model=RCAReportResponse, summary="Get RCA report by ID")
async def get_report(
    report_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> RCAReportResponse:
    """Get a specific RCA report by ID."""
    from src.services.report_service import ReportService

    report_service = ReportService(session)
    report = await report_service.get(report_id)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id} not found",
        )

    return RCAReportResponse.model_validate(report)


@api_router.get("/reports/{report_id}/export", summary="Export RCA report")
async def export_report(
    report_id: UUID,
    format: str = "json",
    session: AsyncSession = Depends(get_session),
):
    """
    Export an RCA report in the specified format.

    Query parameters:
    - format: Export format - "json" (default) or "markdown"
    """
    from fastapi.responses import PlainTextResponse

    from src.services.report_service import ReportService

    report_service = ReportService(session)
    report = await report_service.get(report_id)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id} not found",
        )

    if format.lower() == "markdown":
        markdown_content = report_service.format_as_markdown(report)
        return PlainTextResponse(
            content=markdown_content,
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename=rca-report-{report_id}.md"},
        )
    else:
        # Default to JSON
        return RCAReportResponse.model_validate(report)
