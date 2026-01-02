"""Incident CRUD service."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models import Alert, Incident, IncidentSeverity, IncidentStatus

logger = logging.getLogger(__name__)

# Valid status transitions
VALID_TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.OPEN: {IncidentStatus.ANALYZING, IncidentStatus.RESOLVED, IncidentStatus.CLOSED},
    IncidentStatus.ANALYZING: {IncidentStatus.OPEN, IncidentStatus.RESOLVED, IncidentStatus.CLOSED},
    IncidentStatus.RESOLVED: {IncidentStatus.OPEN, IncidentStatus.CLOSED},
    IncidentStatus.CLOSED: {IncidentStatus.OPEN},  # Allow reopening
}


class IncidentService:
    """Service for Incident CRUD operations."""

    def __init__(self, session: AsyncSession):
        """Initialize the incident service."""
        self.session = session

    async def create(
        self,
        title: str,
        severity: IncidentSeverity,
        started_at: datetime,
        status: IncidentStatus = IncidentStatus.OPEN,
        primary_alert_id: UUID | None = None,
        correlation_reason: str | None = None,
        affected_services: list[str] | None = None,
        affected_labels: dict | None = None,
    ) -> Incident:
        """Create a new incident."""
        incident = Incident(
            title=title,
            status=status,
            severity=severity,
            primary_alert_id=primary_alert_id,
            correlation_reason=correlation_reason,
            affected_services=affected_services or [],
            affected_labels=affected_labels,
            started_at=started_at,
        )
        self.session.add(incident)
        await self.session.flush()
        return incident

    async def get(self, incident_id: UUID) -> Incident | None:
        """Get an incident by ID."""
        return await self.session.get(Incident, incident_id)

    async def get_with_alerts(self, incident_id: UUID) -> Incident | None:
        """Get an incident with its alerts loaded."""
        result = await self.session.execute(
            select(Incident)
            .options(selectinload(Incident.alerts))
            .where(Incident.id == incident_id)
        )
        return result.scalar_one_or_none()

    async def list_incidents(
        self,
        status: IncidentStatus | None = None,
        severity: IncidentSeverity | None = None,
        service: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """
        List incidents with optional filtering (optimized with alert counts).

        Returns:
            tuple: (list of incident dicts with alert_count, total count)
        """
        from sqlalchemy import func

        # Build base filter conditions
        conditions = []
        if status:
            conditions.append(Incident.status == status)
        if severity:
            conditions.append(Incident.severity == severity)
        if service:
            conditions.append(Incident.affected_services.contains([service]))
        if since:
            conditions.append(Incident.started_at >= since)
        if until:
            conditions.append(Incident.started_at <= until)

        # Get total count
        count_query = select(func.count(Incident.id))
        for cond in conditions:
            count_query = count_query.where(cond)
        total = (await self.session.execute(count_query)).scalar_one()

        # Subquery for alert count
        alert_count_subq = (
            select(Alert.incident_id, func.count(Alert.id).label("alert_count"))
            .group_by(Alert.incident_id)
            .subquery()
        )

        # Main query with left join to get alert counts
        query = (
            select(
                Incident,
                func.coalesce(alert_count_subq.c.alert_count, 0).label("alert_count")
            )
            .outerjoin(alert_count_subq, Incident.id == alert_count_subq.c.incident_id)
        )
        for cond in conditions:
            query = query.where(cond)

        query = query.order_by(Incident.started_at.desc()).offset(offset).limit(limit)

        result = await self.session.execute(query)
        rows = result.all()

        # Convert to dicts with alert_count
        incidents_with_counts = []
        for row in rows:
            incident = row[0]
            alert_count = row[1]
            incident_dict = {
                "id": incident.id,
                "title": incident.title,
                "status": incident.status,
                "severity": incident.severity,
                "correlation_reason": incident.correlation_reason,
                "affected_services": incident.affected_services,
                "primary_alert_id": incident.primary_alert_id,
                "affected_labels": incident.affected_labels,
                "started_at": incident.started_at,
                "resolved_at": incident.resolved_at,
                "rca_completed_at": incident.rca_completed_at,
                "created_at": incident.created_at,
                "updated_at": incident.updated_at,
                "alert_count": alert_count,
            }
            incidents_with_counts.append(incident_dict)

        return incidents_with_counts, total

    async def update_status(
        self,
        incident_id: UUID,
        status: IncidentStatus,
        resolved_at: datetime | None = None,
        validate_transition: bool = True,
    ) -> Incident | None:
        """
        Update an incident's status with optional transition validation.

        Args:
            incident_id: Incident ID
            status: New status
            resolved_at: Optional resolution timestamp
            validate_transition: Whether to validate state transition (default True)

        Returns:
            Updated Incident or None if not found or invalid transition
        """
        incident = await self.get(incident_id)
        if not incident:
            return None

        # Validate transition if requested
        if validate_transition:
            valid_next = VALID_TRANSITIONS.get(incident.status, set())
            if status not in valid_next and status != incident.status:
                logger.warning(
                    f"Invalid status transition for incident {incident_id}: "
                    f"{incident.status.value} -> {status.value}"
                )
                return None

        old_status = incident.status
        incident.status = status

        # Auto-set resolved_at for resolution
        if status == IncidentStatus.RESOLVED and not incident.resolved_at:
            incident.resolved_at = resolved_at or datetime.now(UTC)

        await self.session.flush()
        logger.info(f"Incident {incident_id} status: {old_status.value} -> {status.value}")
        return incident

    async def transition_to_analyzing(self, incident_id: UUID) -> Incident | None:
        """Transition incident to ANALYZING status."""
        return await self.update_status(incident_id, IncidentStatus.ANALYZING)

    async def transition_to_resolved(
        self, incident_id: UUID, resolved_at: datetime | None = None
    ) -> Incident | None:
        """Transition incident to RESOLVED status."""
        return await self.update_status(
            incident_id, IncidentStatus.RESOLVED, resolved_at=resolved_at
        )

    async def transition_to_closed(self, incident_id: UUID) -> Incident | None:
        """Transition incident to CLOSED status."""
        return await self.update_status(incident_id, IncidentStatus.CLOSED)

    async def reopen(self, incident_id: UUID) -> Incident | None:
        """Reopen a resolved or closed incident."""
        incident = await self.get(incident_id)
        if incident:
            incident.status = IncidentStatus.OPEN
            incident.resolved_at = None
            await self.session.flush()
            logger.info(f"Incident {incident_id} reopened")
        return incident

    async def set_primary_alert(self, incident_id: UUID, alert_id: UUID) -> Incident | None:
        """Set the primary (root cause) alert for an incident."""
        incident = await self.get(incident_id)
        if incident:
            incident.primary_alert_id = alert_id
            await self.session.flush()
        return incident

    async def add_alert(self, incident_id: UUID, alert: Alert) -> Incident | None:
        """Add an alert to an incident."""
        incident = await self.get(incident_id)
        if incident:
            alert.incident_id = incident_id

            # Update affected services
            new_services = set(incident.affected_services)
            for key in ["service", "app", "job"]:
                if key in alert.labels:
                    new_services.add(alert.labels[key])
            incident.affected_services = list(new_services)

            # Update severity if new alert is more severe
            severity_order = {
                IncidentSeverity.INFO: 0,
                IncidentSeverity.WARNING: 1,
                IncidentSeverity.CRITICAL: 2,
            }
            alert_severity = IncidentSeverity(alert.severity.value)
            if severity_order.get(alert_severity, 0) > severity_order.get(incident.severity, 0):
                incident.severity = alert_severity

            await self.session.flush()
        return incident

    async def delete(self, incident_id: UUID) -> bool:
        """Delete an incident."""
        incident = await self.get(incident_id)
        if incident:
            await self.session.delete(incident)
            await self.session.flush()
            return True
        return False

    async def compute_affected_services(self, incident_id: UUID) -> list[str]:
        """
        Compute affected services from all alerts linked to an incident.

        Args:
            incident_id: Incident ID

        Returns:
            List of unique service names
        """
        incident = await self.get_with_alerts(incident_id)
        if not incident:
            return []

        services: set[str] = set()
        service_labels = ["service", "app", "job", "container", "device"]

        for alert in incident.alerts:
            for label in service_labels:
                if label in (alert.labels or {}):
                    services.add(alert.labels[label])

        return list(services)

    async def update_affected_services(self, incident_id: UUID) -> Incident | None:
        """
        Update incident's affected_services based on all linked alerts.

        Args:
            incident_id: Incident ID

        Returns:
            Updated Incident or None if not found
        """
        incident = await self.get(incident_id)
        if not incident:
            return None

        services = await self.compute_affected_services(incident_id)
        incident.affected_services = services
        await self.session.flush()
        return incident

    async def manual_correlate(
        self,
        incident_id: UUID,
        alert_ids: list[UUID],
    ) -> Incident | None:
        """
        Manually correlate alerts with an incident.

        Args:
            incident_id: Target incident ID
            alert_ids: List of alert IDs to correlate

        Returns:
            Updated Incident or None if not found
        """
        incident = await self.get(incident_id)
        if not incident:
            return None

        # Link each alert
        for alert_id in alert_ids:
            alert = await self.session.get(Alert, alert_id)
            if alert:
                old_incident = alert.incident_id
                alert.incident_id = incident_id
                logger.info(
                    f"Manually correlated alert {alert_id} "
                    f"(from {old_incident}) to incident {incident_id}"
                )

        # Update affected services
        await self.update_affected_services(incident_id)

        # Update correlation reason
        if not incident.correlation_reason:
            incident.correlation_reason = "Manual correlation"
        else:
            incident.correlation_reason += " + Manual correlation"

        await self.session.flush()
        return incident

    async def get_alert_count(self, incident_id: UUID) -> int:
        """Get the number of alerts for an incident."""
        from sqlalchemy import func
        result = await self.session.execute(
            select(func.count()).where(Alert.incident_id == incident_id)
        )
        return result.scalar_one()
