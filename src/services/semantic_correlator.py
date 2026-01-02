"""Semantic correlation using LLM to understand alert relationships."""

from __future__ import annotations

import json
import logging
from typing import Any

from src.models import Alert, Incident
from src.services.llm import LLMProvider

logger = logging.getLogger(__name__)

# Categories of incidents for semantic grouping
INCIDENT_CATEGORIES = {
    "network_connectivity": [
        "interface down", "link down", "carrier lost", "port down",
        "connection refused", "unreachable", "no route", "network partition"
    ],
    "network_congestion": [
        "congestion", "packet drop", "buffer overflow", "queue full",
        "bandwidth saturation", "throttling", "qos violation", "traffic spike"
    ],
    "routing_protocol": [
        "bgp", "ospf", "eigrp", "routing", "neighbor down", "adjacency",
        "route withdrawal", "convergence", "peering"
    ],
    "database_failure": [
        "database", "postgresql", "mysql", "mongodb", "redis",
        "connection pool", "replication", "replica", "primary", "failover"
    ],
    "memory_exhaustion": [
        "oom", "out of memory", "memory leak", "heap", "gc pressure",
        "memory exhaustion", "killed", "evicted"
    ],
    "disk_exhaustion": [
        "disk full", "disk space", "storage", "inode", "quota exceeded",
        "filesystem", "volume"
    ],
    "service_failure": [
        "crash", "error", "exception", "failed", "unavailable",
        "circuit breaker", "timeout", "unhealthy"
    ],
    "latency_degradation": [
        "latency", "slow", "degraded", "response time", "p99", "p95",
        "high latency", "performance"
    ],
}


class SemanticCorrelator:
    """
    Uses LLM to semantically analyze alerts and determine if they share
    the same root cause, rather than just matching labels.
    """

    def __init__(self, llm_provider: LLMProvider):
        """Initialize semantic correlator with LLM provider."""
        self.llm = llm_provider

    def _extract_alert_context(self, alert: Alert) -> str:
        """Extract semantic context from an alert."""
        labels = alert.labels or {}
        annotations = alert.annotations or {}

        context = f"""Alert: {alert.alertname}
Severity: {alert.severity.value}
Service: {labels.get('service', 'unknown')}
Namespace: {labels.get('namespace', 'unknown')}
Datacenter: {labels.get('datacenter', 'unknown')}
Network Segment: {labels.get('network_segment', labels.get('network_path', 'unknown'))}
Summary: {annotations.get('summary', 'N/A')}
Description: {annotations.get('description', 'N/A')}"""

        # Add relevant labels
        relevant_labels = ['node', 'interface', 'cluster', 'upstream', 'downstream', 'peer']
        for label in relevant_labels:
            if label in labels:
                context += f"\n{label}: {labels[label]}"

        return context

    def _extract_incident_context(self, incident: Incident, alerts: list[Alert]) -> str:
        """Extract semantic context from an incident and its alerts."""
        labels = incident.affected_labels or {}

        context = f"""Incident: {incident.title}
Affected Services: {', '.join(incident.affected_services or [])}
Datacenter: {labels.get('datacenter', 'unknown')}
Network Segment: {labels.get('network_segment', labels.get('network_path', 'unknown'))}
Correlation Reason: {incident.correlation_reason or 'N/A'}

Alerts in this incident:"""

        for alert in alerts[:5]:  # Limit to first 5 alerts for context
            annotations = alert.annotations or {}
            context += f"\n- {alert.alertname}: {annotations.get('summary', 'N/A')}"

        return context

    def categorize_alert(self, alert: Alert) -> tuple[str, float]:
        """
        Categorize an alert into an incident category.

        Returns:
            tuple: (category_name, confidence_score)
        """
        alert_text = self._extract_alert_context(alert).lower()

        best_category = "unknown"
        best_score = 0.0

        for category, keywords in INCIDENT_CATEGORIES.items():
            score = sum(1 for kw in keywords if kw in alert_text)
            # Normalize by number of keywords
            normalized_score = score / len(keywords) if keywords else 0
            if normalized_score > best_score:
                best_score = normalized_score
                best_category = category

        return best_category, best_score

    async def are_semantically_related(
        self,
        alert: Alert,
        incident: Incident,
        incident_alerts: list[Alert],
    ) -> tuple[bool, str, float]:
        """
        Use LLM to determine if an alert is semantically related to an incident.

        This goes beyond label matching to understand if the alerts describe
        the same underlying problem.

        Args:
            alert: New alert to evaluate
            incident: Existing incident to compare against
            incident_alerts: List of alerts already in the incident

        Returns:
            tuple: (is_related, reason, confidence)
        """
        alert_context = self._extract_alert_context(alert)
        incident_context = self._extract_incident_context(incident, incident_alerts)

        # First, do a quick category check
        alert_category, alert_score = self.categorize_alert(alert)
        incident_categories = set()
        for inc_alert in incident_alerts:
            cat, _ = self.categorize_alert(inc_alert)
            incident_categories.add(cat)

        # If categories are completely different, likely not related
        if alert_category not in incident_categories and alert_score > 0.3:
            # Different category with high confidence - probably different incident
            if len(incident_categories) == 1 and "unknown" not in incident_categories:
                other_category = list(incident_categories)[0]
                # Check if categories are fundamentally different
                if self._are_categories_incompatible(alert_category, other_category):
                    return False, f"Different incident type: {alert_category} vs {other_category}", 0.8

        # Extract datacenter info for explicit comparison
        alert_labels = alert.labels or {}
        incident_labels = incident.affected_labels or {}
        alert_dc = alert_labels.get('datacenter', 'unknown')
        incident_dc = incident_labels.get('datacenter', 'unknown')
        same_dc = alert_dc == incident_dc

        # Use LLM for deeper semantic analysis
        prompt = f"""Analyze if these two issues should be grouped into the SAME incident or kept SEPARATE.

NEW ALERT (Datacenter: {alert_dc}):
{alert_context}

EXISTING INCIDENT (Datacenter: {incident_dc}):
{incident_context}

CRITICAL: The alert is in datacenter '{alert_dc}' and the incident is in datacenter '{incident_dc}'.
These are {'THE SAME' if same_dc else 'DIFFERENT'} datacenters.

Rules:
1. DIFFERENT datacenters = SEPARATE incidents (related: false) unless there's a clear upstream/downstream dependency
2. SAME datacenter + SAME network segment + related issue type = SAME incident (related: true)
3. SAME datacenter + SAME device = SAME incident (related: true)

Respond with JSON:
{{
    "related": true/false,
    "confidence": 0.0-1.0,
    "reason": "brief explanation"
}}"""

        try:
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.1,
            )

            if response.content:
                # Parse JSON response
                result = self._parse_llm_response(response.content)
                return (
                    result.get("related", False),
                    result.get("reason", "LLM analysis"),
                    result.get("confidence", 0.5),
                )
        except Exception as e:
            logger.warning(f"LLM semantic analysis failed: {e}")

        # Fallback to category-based decision
        if alert_category in incident_categories:
            return True, f"Same incident category: {alert_category}", 0.6

        return False, "Unable to determine relationship", 0.3

    def _are_categories_incompatible(self, cat1: str, cat2: str) -> bool:
        """Check if two categories are fundamentally incompatible."""
        incompatible_pairs = [
            ("network_connectivity", "memory_exhaustion"),
            ("network_connectivity", "disk_exhaustion"),
            ("network_congestion", "database_failure"),
            ("network_congestion", "memory_exhaustion"),
            ("routing_protocol", "disk_exhaustion"),
            ("memory_exhaustion", "disk_exhaustion"),
        ]

        for pair in incompatible_pairs:
            if (cat1, cat2) in [pair, (pair[1], pair[0])]:
                return True

        return False

    def _parse_llm_response(self, content: str) -> dict[str, Any]:
        """Parse LLM response, handling potential formatting issues."""
        # Try to extract JSON from response
        content = content.strip()

        # Handle markdown code blocks
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            content = content[start:end].strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract key fields manually
            result = {"related": False, "confidence": 0.5, "reason": "Parse error"}

            content_lower = content.lower()
            if '"related": true' in content_lower or '"related":true' in content_lower or "related" in content_lower and "true" in content_lower:
                result["related"] = True

            return result

    async def find_best_incident(
        self,
        alert: Alert,
        candidate_incidents: list[tuple[Incident, list[Alert]]],
    ) -> tuple[Incident | None, str, float]:
        """
        Find the best matching incident for an alert using semantic analysis.

        Args:
            alert: New alert to match
            candidate_incidents: List of (incident, alerts) tuples to consider

        Returns:
            tuple: (best_incident, reason, confidence) or (None, reason, 0.0)
        """
        best_match = None
        best_reason = "No semantic match found"
        best_confidence = 0.0

        for incident, incident_alerts in candidate_incidents:
            is_related, reason, confidence = await self.are_semantically_related(
                alert, incident, incident_alerts
            )

            if is_related and confidence > best_confidence:
                best_match = incident
                best_reason = reason
                best_confidence = confidence

        return best_match, best_reason, best_confidence
