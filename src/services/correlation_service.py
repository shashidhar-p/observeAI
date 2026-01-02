"""Alert correlation service for grouping related alerts."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models import Alert, Incident, IncidentSeverity, IncidentStatus

if TYPE_CHECKING:
    from src.services.llm import LLMProvider

logger = logging.getLogger(__name__)
settings = get_settings()


class CorrelationService:
    """
    Service for correlating related alerts into incidents.

    Correlation is based on:
    1. Time window: Alerts within a configurable time window
    2. Label matching: Alerts sharing common labels (service, namespace, node)
    3. Cross-namespace correlation: Infrastructure labels (datacenter, network_segment)
    4. Reference matching: Alerts referencing other nodes/services
    5. Causal analysis: Identifying primary vs symptom alerts
    """

    # Primary correlation labels (direct match)
    CORRELATION_LABELS = ["service", "namespace", "node", "instance", "job", "app"]

    # Infrastructure labels for cross-namespace correlation
    INFRASTRUCTURE_LABELS = ["datacenter", "network_segment", "cluster", "zone", "region", "rack", "network_path"]

    # Labels that reference other entities (cross-reference)
    CROSS_REFERENCE_LABELS = ["target_node", "destination", "source", "peer", "upstream", "downstream", "dependency"]

    # Alert patterns that indicate infrastructure issues (likely root causes)
    INFRASTRUCTURE_ALERT_PATTERNS = [
        "interface", "bgp", "ospf", "network", "route", "switch", "router",
        "connectivity", "partition", "unreachable", "carrier", "link"
    ]

    # Label priority for primary alert detection
    CAUSAL_INDICATORS = {
        # Infrastructure alerts - highest priority (root causes)
        "interface": 15,
        "bgp": 14,
        "ospf": 13,
        "route": 12,
        "network": 11,
        "carrier": 14,
        "partition": 13,
        # Resource exhaustion alerts
        "disk": 10,
        "memory": 9,
        "cpu": 8,
        "storage": 10,
        "oom": 9,
        "quota": 8,
        # Symptom alerts - lower priority
        "health": 3,
        "unavailable": 2,
        "error": 4,
        "timeout": 3,
        "latency": 3,
        "connectivity": 5,
    }

    def __init__(self, session: AsyncSession, llm_provider: LLMProvider | None = None):
        """Initialize the correlation service."""
        self.session = session
        self.window_seconds = settings.correlation_window_seconds
        self.llm_provider = llm_provider
        self._semantic_correlator = None

    @property
    def semantic_correlator(self):
        """Lazy-load semantic correlator."""
        if self._semantic_correlator is None and self.llm_provider is not None:
            from src.services.semantic_correlator import SemanticCorrelator
            self._semantic_correlator = SemanticCorrelator(self.llm_provider)
        return self._semantic_correlator

    async def find_related_incident(self, alert: Alert) -> Incident | None:
        """
        Find an existing incident that this alert should be correlated with.

        Uses a two-phase approach:
        1. Label-based scoring to find candidates
        2. Semantic analysis to verify they're actually related

        Args:
            alert: The new alert to correlate

        Returns:
            Incident if a related one is found, None otherwise
        """
        # Define time window
        window_start = alert.starts_at - timedelta(seconds=self.window_seconds)
        window_end = alert.starts_at + timedelta(seconds=self.window_seconds)

        # Find incidents within the time window
        query = select(Incident).where(
            and_(
                Incident.started_at >= window_start,
                Incident.started_at <= window_end,
                Incident.status.in_([IncidentStatus.OPEN, IncidentStatus.ANALYZING]),
            )
        )

        result = await self.session.execute(query)
        candidates = list(result.scalars().all())

        if not candidates:
            return None

        # Score each candidate by label overlap
        scored_candidates = []
        for incident in candidates:
            score = self._calculate_correlation_score(alert, incident)
            if score >= 2:  # Minimum score threshold
                scored_candidates.append((incident, score))

        if not scored_candidates:
            return None

        # Sort by score descending
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # Always use LLM semantic correlation when enabled and available
        if settings.semantic_correlation_enabled and self.semantic_correlator is not None:
            logger.info(f"Using LLM semantic correlation for {alert.alertname} ({len(scored_candidates)} candidates)")
            try:
                # Get alerts for each candidate incident
                candidate_with_alerts = []
                for incident, _score in scored_candidates:
                    alerts_result = await self.session.execute(
                        select(Alert).where(Alert.incident_id == incident.id)
                    )
                    incident_alerts = list(alerts_result.scalars().all())
                    candidate_with_alerts.append((incident, incident_alerts))

                best_match, reason, confidence = await self.semantic_correlator.find_best_incident(
                    alert, candidate_with_alerts
                )

                if best_match and confidence >= 0.6:
                    logger.info(
                        f"Semantic correlation: {alert.alertname} -> {best_match.id} "
                        f"(confidence: {confidence:.2f}, reason: {reason})"
                    )
                    return best_match
                elif best_match is None:
                    logger.info(
                        f"Semantic analysis rejected correlation for {alert.alertname}: {reason}"
                    )
                    return None

            except Exception as e:
                logger.warning(f"Semantic correlation failed, falling back to label-based: {e}")

        # Fall back to best label-based match
        best_match = scored_candidates[0][0]
        best_score = scored_candidates[0][1]

        logger.info(
            f"Correlated alert {alert.alertname} with incident {best_match.id} "
            f"(score: {best_score})"
        )
        return best_match

    def _calculate_correlation_score(self, alert: Alert, incident: Incident) -> int:
        """
        Calculate correlation score between an alert and an incident.

        Uses multiple correlation strategies:
        1. Direct label matching (service, namespace, node)
        2. Infrastructure label matching (datacenter, network_segment)
        3. Cross-reference matching (target_node references)
        4. Infrastructure alert affinity (network issues correlate with symptoms)

        Args:
            alert: Alert to score
            incident: Incident to compare against

        Returns:
            int: Correlation score (higher = more related)
        """
        score = 0
        alert_labels = alert.labels or {}
        incident_labels = incident.affected_labels or {}

        # 1. Direct label matching
        for label in self.CORRELATION_LABELS:
            if label in alert_labels and label in incident_labels:
                if alert_labels[label] == incident_labels[label]:
                    score += 2  # Exact match
                elif self._partial_match(alert_labels[label], incident_labels[label]):
                    score += 1  # Partial match

        # 2. Infrastructure label matching (cross-namespace correlation)
        for label in self.INFRASTRUCTURE_LABELS:
            if label in alert_labels and label in incident_labels:
                if alert_labels[label] == incident_labels[label]:
                    score += 4  # Infrastructure match is strong indicator
                    logger.debug(f"Infrastructure label match: {label}={alert_labels[label]}")

        # 3. Cross-reference matching
        score += self._calculate_cross_reference_score(alert, incident)

        # 4. Infrastructure alert affinity
        score += self._calculate_infrastructure_affinity(alert, incident)

        # Bonus for same service
        if alert_labels.get("service") == incident_labels.get("service"):
            score += 3

        # Bonus for same namespace
        if alert_labels.get("namespace") == incident_labels.get("namespace"):
            score += 2

        return score

    def _calculate_cross_reference_score(self, alert: Alert, incident: Incident) -> int:
        """
        Calculate score based on cross-references between alerts.

        Checks if alert references nodes/services mentioned in the incident.
        """
        score = 0
        alert_labels = alert.labels or {}
        incident_labels = incident.affected_labels or {}
        incident_services = set(incident.affected_services or [])

        # Check if alert references any entity from the incident
        for ref_label in self.CROSS_REFERENCE_LABELS:
            if ref_label in alert_labels:
                ref_value = alert_labels[ref_label]
                # Check against incident node
                if ref_value == incident_labels.get("node"):
                    score += 5
                    logger.debug(f"Cross-reference match: {ref_label} -> incident node")
                # Check against incident service
                if ref_value in incident_services:
                    score += 4
                    logger.debug(f"Cross-reference match: {ref_label} -> incident service")

        # Check if incident references entities from this alert
        for ref_label in self.CROSS_REFERENCE_LABELS:
            if ref_label in incident_labels:
                ref_value = incident_labels[ref_label]
                if ref_value == alert_labels.get("node"):
                    score += 5
                if ref_value == alert_labels.get("service"):
                    score += 4

        # Check annotations for service/node mentions
        score += self._check_annotation_references(alert, incident)

        return score

    def _check_annotation_references(self, alert: Alert, incident: Incident) -> int:
        """Check if annotations mention related entities."""
        score = 0
        alert_annotations = alert.annotations or {}
        incident_labels = incident.affected_labels or {}
        incident_services = set(incident.affected_services or [])

        # Combine description and summary for checking
        alert_text = " ".join([
            str(alert_annotations.get("description", "")),
            str(alert_annotations.get("summary", "")),
        ]).lower()

        # Check if alert text mentions incident node
        incident_node = incident_labels.get("node", "")
        if incident_node and incident_node.lower() in alert_text:
            score += 3
            logger.debug(f"Annotation reference: incident node '{incident_node}' found in alert text")

        # Check if alert text mentions incident service
        for service in incident_services:
            if service and service.lower() in alert_text:
                score += 2
                logger.debug(f"Annotation reference: service '{service}' found in alert text")

        return score

    def _calculate_infrastructure_affinity(self, alert: Alert, incident: Incident) -> int:
        """
        Calculate infrastructure affinity score.

        Infrastructure alerts (network, interface, BGP) should correlate
        with symptom alerts (timeout, latency, connectivity) even across namespaces.
        """
        score = 0
        alert_labels = alert.labels or {}
        incident_labels = incident.affected_labels or {}

        alert_name_lower = alert.alertname.lower()
        is_alert_infra = any(pattern in alert_name_lower for pattern in self.INFRASTRUCTURE_ALERT_PATTERNS)

        # Get incident's primary alert name if available
        incident_is_infra = self._incident_has_infra_alert(incident)

        # Infrastructure alert correlating with non-infra namespace
        if is_alert_infra and incident_labels.get("namespace") not in ["network-infra", "infrastructure", "networking"]:
            # If they share a datacenter, they're likely related
            if alert_labels.get("datacenter") == incident_labels.get("datacenter"):
                score += 3
                logger.debug("Infrastructure affinity: infra alert + shared datacenter")

        # Non-infra alert correlating with infrastructure incident
        if incident_is_infra and alert_labels.get("namespace") not in ["network-infra", "infrastructure", "networking"]:
            if alert_labels.get("datacenter") == incident_labels.get("datacenter"):
                score += 3
                logger.debug("Infrastructure affinity: infra incident + shared datacenter")

            # Check network path matching
            if alert_labels.get("network_path") == incident_labels.get("network_segment"):
                score += 4

        return score

    def _incident_has_infra_alert(self, incident: Incident) -> bool:
        """Check if incident has an infrastructure-related alert."""
        title_lower = incident.title.lower() if incident.title else ""
        return any(pattern in title_lower for pattern in self.INFRASTRUCTURE_ALERT_PATTERNS)

    def _partial_match(self, value1: str, value2: str) -> bool:
        """Check if two values partially match (e.g., pod names with random suffixes)."""
        # Extract base name (before last hyphen for pod names)
        base1 = value1.rsplit("-", 1)[0] if "-" in value1 else value1
        base2 = value2.rsplit("-", 1)[0] if "-" in value2 else value2
        return base1 == base2

    async def correlate_alert(self, alert: Alert) -> tuple[Incident, bool]:
        """
        Correlate an alert with an existing incident or create a new one.

        Args:
            alert: The alert to correlate

        Returns:
            tuple: (Incident, is_new_incident)
        """
        # Try to find existing incident
        existing = await self.find_related_incident(alert)

        if existing:
            # Update existing incident
            await self._add_alert_to_incident(alert, existing)
            return existing, False
        else:
            # Create new incident
            incident = await self._create_incident_for_alert(alert)
            return incident, True

    async def _add_alert_to_incident(self, alert: Alert, incident: Incident) -> None:
        """Add an alert to an existing incident."""
        # Link alert to incident
        alert.incident_id = incident.id

        # Update affected services (including device for network equipment)
        new_services = set(incident.affected_services or [])
        for key in ["service", "app", "job", "device"]:
            if key in (alert.labels or {}):
                new_services.add(alert.labels[key])
        incident.affected_services = list(new_services)

        # Update affected labels (merge) - include infrastructure labels
        if incident.affected_labels is None:
            incident.affected_labels = {}
        all_labels = self.CORRELATION_LABELS + self.INFRASTRUCTURE_LABELS
        for key in all_labels:
            if key in (alert.labels or {}) and key not in incident.affected_labels:
                incident.affected_labels[key] = alert.labels[key]

        # Update severity if new alert is more severe
        alert_severity = IncidentSeverity(alert.severity.value)
        severity_order = {
            IncidentSeverity.INFO: 0,
            IncidentSeverity.WARNING: 1,
            IncidentSeverity.CRITICAL: 2,
        }
        if severity_order.get(alert_severity, 0) > severity_order.get(incident.severity, 0):
            incident.severity = alert_severity

        # Update correlation reason
        incident.correlation_reason = self._generate_correlation_reason(alert, incident)

        # Re-evaluate primary alert
        await self._update_primary_alert(incident)

        await self.session.flush()

    async def _create_incident_for_alert(self, alert: Alert) -> Incident:
        """Create a new incident for an alert."""
        # Determine severity
        try:
            severity = IncidentSeverity(alert.severity.value)
        except ValueError:
            severity = IncidentSeverity.WARNING

        # Extract services (including device for network equipment)
        services = []
        for key in ["service", "app", "job", "device"]:
            if key in (alert.labels or {}):
                services.append(alert.labels[key])

        # Include both correlation and infrastructure labels
        all_labels = self.CORRELATION_LABELS + self.INFRASTRUCTURE_LABELS
        affected_labels = {
            k: v for k, v in (alert.labels or {}).items()
            if k in all_labels
        }

        incident = Incident(
            title=alert.alertname,
            status=IncidentStatus.OPEN,
            severity=severity,
            affected_services=list(set(services)),
            affected_labels=affected_labels,
            started_at=alert.starts_at,
        )

        self.session.add(incident)
        await self.session.flush()

        # Link alert to incident
        alert.incident_id = incident.id

        # Set as primary alert
        incident.primary_alert_id = alert.id

        await self.session.flush()

        logger.info(f"Created new incident {incident.id} for alert {alert.alertname}")
        return incident

    async def _update_primary_alert(self, incident: Incident) -> None:
        """
        Update the primary (root cause) alert for an incident.

        Uses chronological order and causal indicators to determine
        which alert is most likely the root cause.
        """
        # Get all alerts for this incident
        result = await self.session.execute(
            select(Alert)
            .where(Alert.incident_id == incident.id)
            .order_by(Alert.starts_at.asc())
        )
        alerts = list(result.scalars().all())

        if not alerts:
            return

        # Score each alert
        best_alert = alerts[0]  # Default to chronologically first
        best_score = self._calculate_causal_score(best_alert)

        for alert in alerts[1:]:
            score = self._calculate_causal_score(alert)
            # Prefer higher causal score, but give bonus to earlier alerts
            time_bonus = 1 if alert.starts_at == alerts[0].starts_at else 0
            if score + time_bonus > best_score:
                best_score = score
                best_alert = alert

        incident.primary_alert_id = best_alert.id

    def _calculate_causal_score(self, alert: Alert) -> int:
        """Calculate how likely this alert is to be a root cause."""
        score = 0
        alertname = alert.alertname.lower()

        for indicator, points in self.CAUSAL_INDICATORS.items():
            if indicator in alertname:
                score += points

        # Critical alerts are more likely to be root cause
        if alert.severity.value == "critical":
            score += 5

        return score

    def _generate_correlation_reason(self, alert: Alert, incident: Incident) -> str:
        """Generate a human-readable correlation reason."""
        reasons = []
        alert_labels = alert.labels or {}
        incident_labels = incident.affected_labels or {}

        # Check for direct label matches
        for label in self.CORRELATION_LABELS:
            if label in alert_labels and label in incident_labels:
                if alert_labels[label] == incident_labels[label]:
                    reasons.append(f"same {label}: {alert_labels[label]}")

        # Check for infrastructure label matches (cross-namespace)
        for label in self.INFRASTRUCTURE_LABELS:
            if label in alert_labels and label in incident_labels:
                if alert_labels[label] == incident_labels[label]:
                    reasons.append(f"shared {label}: {alert_labels[label]}")

        # Check for cross-reference matches
        for ref_label in self.CROSS_REFERENCE_LABELS:
            if ref_label in alert_labels:
                if alert_labels[ref_label] == incident_labels.get("node"):
                    reasons.append(f"{ref_label} references incident node")
                elif alert_labels[ref_label] in (incident.affected_services or []):
                    reasons.append(f"{ref_label} references incident service")

        # Check for infrastructure affinity
        alert_name_lower = alert.alertname.lower()
        is_infra = any(p in alert_name_lower for p in self.INFRASTRUCTURE_ALERT_PATTERNS)
        incident_is_infra = self._incident_has_infra_alert(incident)

        if is_infra and not incident_is_infra:
            if alert_labels.get("datacenter") == incident_labels.get("datacenter"):
                reasons.append("infrastructure alert in same datacenter")
        elif incident_is_infra and not is_infra:
            reasons.append("symptom of infrastructure incident")

        if reasons:
            return f"Correlated by {', '.join(reasons[:4])}"
        else:
            return "Correlated by time proximity"

    async def get_correlation_timeline(self, incident_id: UUID) -> list[dict]:
        """
        Get a timeline of correlated alerts for an incident.

        Args:
            incident_id: Incident ID

        Returns:
            list: Chronologically ordered list of alert events
        """
        result = await self.session.execute(
            select(Alert)
            .where(Alert.incident_id == incident_id)
            .order_by(Alert.starts_at.asc())
        )
        alerts = list(result.scalars().all())

        timeline = []
        for alert in alerts:
            timeline.append({
                "timestamp": alert.starts_at.isoformat(),
                "event": f"{alert.alertname}: {(alert.annotations or {}).get('summary', alert.alertname)}",
                "source": "alert",
                "alert_id": str(alert.id),
                "severity": alert.severity.value,
                "is_primary": alert.id == (await self.session.get(Incident, incident_id)).primary_alert_id,
            })

        return timeline
