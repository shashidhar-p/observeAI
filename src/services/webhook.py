"""Alert Manager webhook handler service."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import AlertManagerAlert, AlertManagerWebhookPayload
from src.models import Alert, AlertSeverity, AlertStatus, Incident
from src.services.alert_service import AlertService
from src.services.correlation_service import CorrelationService
from src.services.incident_service import IncidentService

if TYPE_CHECKING:
    from src.services.llm import LLMProvider

logger = logging.getLogger(__name__)


class WebhookService:
    """
    Service for handling Alert Manager webhooks.

    Handles alert parsing, deduplication, correlation, and triggers RCA processing.
    """

    def __init__(self, session: AsyncSession, llm_provider: LLMProvider | None = None):
        """Initialize the webhook service."""
        self.session = session
        self.alert_service = AlertService(session)
        self.incident_service = IncidentService(session)
        self.correlation_service = CorrelationService(session, llm_provider=llm_provider)

    async def process_webhook(
        self,
        payload: AlertManagerWebhookPayload,
    ) -> tuple[list[UUID], list[UUID]]:
        """
        Process an Alert Manager webhook payload.

        Args:
            payload: Alert Manager webhook payload

        Returns:
            tuple: (list of created/updated alert IDs, list of incident IDs to process)
        """
        alert_ids = []
        incident_ids = set()

        for am_alert in payload.alerts:
            try:
                # Check for duplicate
                existing = await self.alert_service.get_by_fingerprint(am_alert.fingerprint)

                if existing:
                    # Check if this is a re-firing alert (was resolved, now firing again)
                    # AND its incident is already resolved - create new incident
                    if (existing.status == AlertStatus.RESOLVED and
                        am_alert.status.value == "firing" and
                        existing.incident_id):
                        incident = await self.incident_service.get(existing.incident_id)
                        if incident and incident.status.value == "resolved":
                            # Create NEW alert and incident for this re-occurrence
                            logger.info(f"Alert {am_alert.fingerprint} re-firing after incident resolved - creating new incident")
                            alert = await self._create_alert_with_new_fingerprint(am_alert)
                            alert_ids.append(alert.id)
                            new_incident, _ = await self._ensure_incident(alert)
                            incident_ids.add(new_incident.id)
                            continue

                    # Update existing alert if status changed
                    if existing.status.value != am_alert.status.value:
                        await self._update_alert_status(existing, am_alert)
                        alert_ids.append(existing.id)
                        if existing.incident_id:
                            incident_ids.add(existing.incident_id)
                    else:
                        logger.debug(f"Duplicate alert ignored: {am_alert.fingerprint}")
                else:
                    # Create new alert
                    alert = await self._create_alert(am_alert)
                    alert_ids.append(alert.id)

                    # Correlate with existing incident or create new one
                    incident, is_new = await self._ensure_incident(alert)
                    incident_ids.add(incident.id)

            except Exception as e:
                logger.exception(f"Failed to process alert {am_alert.fingerprint}: {e}")

        return alert_ids, list(incident_ids)

    async def _create_alert_with_new_fingerprint(self, am_alert: AlertManagerAlert) -> Alert:
        """Create a new alert with a unique fingerprint for re-occurring alerts."""
        import uuid
        # Generate a new unique fingerprint by appending a UUID suffix
        new_fingerprint = f"{am_alert.fingerprint}_{uuid.uuid4().hex[:8]}"

        # Create a modified alert with the new fingerprint
        modified_alert = AlertManagerAlert(
            status=am_alert.status,
            labels=am_alert.labels,
            annotations=am_alert.annotations,
            startsAt=am_alert.startsAt,
            endsAt=am_alert.endsAt,
            generatorURL=am_alert.generatorURL,
            fingerprint=new_fingerprint,
        )
        return await self._create_alert(modified_alert)

    async def _create_alert(self, am_alert: AlertManagerAlert) -> Alert:
        """Create a new alert from Alert Manager data."""
        # Map severity
        severity_str = am_alert.labels.get("severity", "warning").lower()
        try:
            severity = AlertSeverity(severity_str)
        except ValueError:
            severity = AlertSeverity.WARNING

        # Map status
        try:
            status = AlertStatus(am_alert.status.value)
        except ValueError:
            status = AlertStatus.FIRING

        alert = Alert(
            fingerprint=am_alert.fingerprint,
            alertname=am_alert.labels.get("alertname", "Unknown"),
            severity=severity,
            status=status,
            labels=am_alert.labels,
            annotations=am_alert.annotations,
            starts_at=am_alert.startsAt,
            ends_at=am_alert.endsAt if am_alert.endsAt and am_alert.endsAt.year > 1 else None,
            generator_url=am_alert.generatorURL,
            received_at=datetime.now(UTC),
        )

        self.session.add(alert)
        await self.session.flush()

        logger.info(f"Created alert: {alert.alertname} ({alert.severity.value})")
        return alert

    async def _update_alert_status(self, alert: Alert, am_alert: AlertManagerAlert) -> None:
        """Update an existing alert's status."""
        try:
            new_status = AlertStatus(am_alert.status.value)
        except ValueError:
            new_status = AlertStatus.RESOLVED

        old_status = alert.status
        alert.status = new_status

        if new_status == AlertStatus.RESOLVED:
            alert.ends_at = am_alert.endsAt if am_alert.endsAt and am_alert.endsAt.year > 1 else datetime.now(UTC)

        await self.session.flush()
        logger.info(f"Updated alert {alert.alertname}: {old_status.value} -> {new_status.value}")

        # Check if all alerts in the incident are now resolved
        if new_status == AlertStatus.RESOLVED and alert.incident_id:
            await self._check_incident_resolution(alert.incident_id)

    async def _check_incident_resolution(self, incident_id: UUID) -> None:
        """
        Check if all alerts in an incident are resolved.

        If all alerts are resolved, transition the incident to RESOLVED status.
        """
        from src.models import IncidentStatus

        incident = await self.incident_service.get_with_alerts(incident_id)
        if not incident:
            logger.warning(f"Incident {incident_id} not found for resolution check")
            return

        # Count firing alerts
        firing_alerts = [a for a in incident.alerts if a.status == AlertStatus.FIRING]

        if len(firing_alerts) == 0:
            # All alerts are resolved, transition incident to RESOLVED
            if incident.status != IncidentStatus.RESOLVED:
                incident.status = IncidentStatus.RESOLVED
                incident.resolved_at = datetime.now(UTC)
                await self.session.flush()
                logger.info(
                    f"Incident {incident_id} auto-resolved: all {len(incident.alerts)} alerts are now resolved"
                )
        else:
            logger.debug(
                f"Incident {incident_id} still has {len(firing_alerts)} firing alerts"
            )

    async def _ensure_incident(self, alert: Alert) -> tuple[Incident, bool]:
        """
        Ensure an incident exists for the alert using correlation.

        Uses the correlation service to find related incidents or create new ones.
        Related alerts are grouped into the same incident based on:
        - Time window proximity
        - Label matching (service, namespace, node, etc.)
        - Causal analysis for primary alert detection

        Returns:
            tuple: (Incident, is_new_incident)
        """
        incident, is_new = await self.correlation_service.correlate_alert(alert)

        if is_new:
            logger.info(f"Created new incident: {incident.title} for alert {alert.alertname}")
        else:
            logger.info(
                f"Correlated alert {alert.alertname} with existing incident {incident.id} "
                f"(reason: {incident.correlation_reason})"
            )

        return incident, is_new

    def _extract_services(self, labels: dict) -> list[str]:
        """Extract service names from alert labels."""
        services = []
        for key in ["service", "app", "job", "container"]:
            if key in labels:
                services.append(labels[key])
        return list(set(services))
