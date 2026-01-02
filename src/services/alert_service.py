"""Alert CRUD service."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Alert, AlertSeverity, AlertStatus

logger = logging.getLogger(__name__)


class AlertService:
    """Service for Alert CRUD operations."""

    def __init__(self, session: AsyncSession):
        """Initialize the alert service."""
        self.session = session

    async def create(
        self,
        fingerprint: str,
        alertname: str,
        severity: AlertSeverity,
        status: AlertStatus,
        labels: dict,
        starts_at: datetime,
        annotations: dict | None = None,
        ends_at: datetime | None = None,
        generator_url: str | None = None,
        incident_id: UUID | None = None,
    ) -> Alert:
        """Create a new alert."""
        alert = Alert(
            fingerprint=fingerprint,
            alertname=alertname,
            severity=severity,
            status=status,
            labels=labels,
            annotations=annotations,
            starts_at=starts_at,
            ends_at=ends_at,
            generator_url=generator_url,
            incident_id=incident_id,
        )
        self.session.add(alert)
        await self.session.flush()
        return alert

    async def get(self, alert_id: UUID) -> Alert | None:
        """Get an alert by ID."""
        return await self.session.get(Alert, alert_id)

    async def get_by_fingerprint(self, fingerprint: str) -> Alert | None:
        """Get an alert by fingerprint."""
        result = await self.session.execute(
            select(Alert).where(Alert.fingerprint == fingerprint)
        )
        return result.scalar_one_or_none()

    async def list_alerts(
        self,
        status: AlertStatus | None = None,
        severity: AlertSeverity | None = None,
        service: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Alert], int]:
        """
        List alerts with optional filtering.

        Returns:
            tuple: (list of alerts, total count)
        """
        query = select(Alert)

        # Apply filters
        if status:
            query = query.where(Alert.status == status)
        if severity:
            query = query.where(Alert.severity == severity)
        if service:
            query = query.where(Alert.labels["service"].astext == service)
        if since:
            query = query.where(Alert.starts_at >= since)
        if until:
            query = query.where(Alert.starts_at <= until)

        # Get total count
        from sqlalchemy import func
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar_one()

        # Apply pagination and ordering
        query = query.order_by(Alert.starts_at.desc()).offset(offset).limit(limit)

        result = await self.session.execute(query)
        alerts = result.scalars().all()

        return list(alerts), total

    async def list_by_incident(self, incident_id: UUID) -> list[Alert]:
        """Get all alerts for an incident."""
        result = await self.session.execute(
            select(Alert)
            .where(Alert.incident_id == incident_id)
            .order_by(Alert.starts_at.asc())
        )
        return list(result.scalars().all())

    async def update_status(self, alert_id: UUID, status: AlertStatus, ends_at: datetime | None = None) -> Alert | None:
        """Update an alert's status."""
        alert = await self.get(alert_id)
        if alert:
            alert.status = status
            if ends_at:
                alert.ends_at = ends_at
            await self.session.flush()
        return alert

    async def link_to_incident(self, alert_id: UUID, incident_id: UUID) -> Alert | None:
        """Link an alert to an incident."""
        alert = await self.get(alert_id)
        if alert:
            alert.incident_id = incident_id
            await self.session.flush()
        return alert

    async def delete(self, alert_id: UUID) -> bool:
        """Delete an alert."""
        alert = await self.get(alert_id)
        if alert:
            await self.session.delete(alert)
            await self.session.flush()
            return True
        return False
