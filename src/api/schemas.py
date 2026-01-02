"""Pydantic schemas for API request/response models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

# ============================================================================
# Base Response Schemas
# ============================================================================


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: dict | None = Field(default=None, description="Additional error details")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Health status: healthy or unhealthy")
    version: str = Field(..., description="Application version")
    uptime_seconds: int = Field(..., description="Server uptime in seconds")


class ReadinessCheck(BaseModel):
    """Individual readiness check result."""

    database: bool = Field(..., description="Database connection status")
    loki: bool = Field(..., description="Loki connection status")
    cortex: bool = Field(..., description="Cortex connection status")
    llm: bool = Field(..., description="LLM API status")


class ReadinessResponse(BaseModel):
    """Readiness check response."""

    ready: bool = Field(..., description="Overall readiness status")
    checks: ReadinessCheck = Field(..., description="Individual check results")


# ============================================================================
# Enums
# ============================================================================


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertStatus(str, Enum):
    """Alert status."""

    FIRING = "firing"
    RESOLVED = "resolved"


class IncidentStatus(str, Enum):
    """Incident status."""

    OPEN = "open"
    ANALYZING = "analyzing"
    RESOLVED = "resolved"
    CLOSED = "closed"


class RCAReportStatus(str, Enum):
    """RCA report status."""

    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"


class RemediationPriority(str, Enum):
    """Remediation step priority."""

    IMMEDIATE = "immediate"
    LONG_TERM = "long_term"


class RiskLevel(str, Enum):
    """Risk level for remediation steps."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ============================================================================
# Alert Manager Webhook Schemas
# ============================================================================


class AlertManagerAlert(BaseModel):
    """Individual alert from Alert Manager."""

    status: AlertStatus
    labels: dict[str, str] = Field(..., description="Alert labels")
    annotations: dict[str, str] = Field(default_factory=dict, description="Alert annotations")
    startsAt: datetime = Field(..., alias="startsAt", description="Alert start time")
    endsAt: datetime | None = Field(default=None, alias="endsAt", description="Alert end time")
    generatorURL: str | None = Field(
        default=None, alias="generatorURL", description="Alert source URL"
    )
    fingerprint: str = Field(..., description="Alert fingerprint for deduplication")

    model_config = {"populate_by_name": True}


class AlertManagerWebhookPayload(BaseModel):
    """Alert Manager webhook payload."""

    receiver: str = Field(..., description="Receiver name")
    status: AlertStatus = Field(..., description="Overall status")
    alerts: list[AlertManagerAlert] = Field(..., description="List of alerts")
    groupLabels: dict[str, str] = Field(
        default_factory=dict, alias="groupLabels", description="Group labels"
    )
    commonLabels: dict[str, str] = Field(
        default_factory=dict, alias="commonLabels", description="Common labels"
    )
    commonAnnotations: dict[str, str] = Field(
        default_factory=dict, alias="commonAnnotations", description="Common annotations"
    )
    externalURL: str | None = Field(
        default=None, alias="externalURL", description="Alert Manager URL"
    )
    version: str | None = Field(default=None, description="API version")
    groupKey: str | None = Field(default=None, alias="groupKey", description="Group key")
    truncatedAlerts: int = Field(
        default=0, alias="truncatedAlerts", description="Number of truncated alerts"
    )

    model_config = {"populate_by_name": True}


class WebhookAcceptedResponse(BaseModel):
    """Response for accepted webhook."""

    status: str = Field(default="accepted", description="Status")
    message: str = Field(..., description="Status message")
    alerts_received: int = Field(..., description="Number of alerts received")
    processing_ids: list[UUID] = Field(..., description="IDs of alerts being processed")


# ============================================================================
# Alert Schemas
# ============================================================================


class AlertBase(BaseModel):
    """Base alert schema."""

    fingerprint: str
    alertname: str
    severity: AlertSeverity
    status: AlertStatus
    labels: dict[str, str]
    annotations: dict[str, str] | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    generator_url: str | None = None


class AlertCreate(AlertBase):
    """Schema for creating an alert."""

    pass


class AlertResponse(AlertBase):
    """Alert response schema."""

    id: UUID
    incident_id: UUID | None = None
    received_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    """Paginated list of alerts."""

    alerts: list[AlertResponse]
    total: int
    limit: int
    offset: int


# ============================================================================
# Incident Schemas
# ============================================================================


class IncidentBase(BaseModel):
    """Base incident schema."""

    title: str
    status: IncidentStatus
    severity: AlertSeverity
    correlation_reason: str | None = None
    affected_services: list[str] = Field(default_factory=list)


class IncidentCreate(IncidentBase):
    """Schema for creating an incident."""

    pass


class IncidentResponse(IncidentBase):
    """Incident response schema with full alerts - for single incident detail view."""

    id: UUID
    primary_alert_id: UUID | None = None
    affected_labels: dict[str, str] | None = None
    started_at: datetime
    resolved_at: datetime | None = None
    rca_completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    alerts: list[AlertResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class IncidentSummary(IncidentBase):
    """Incident summary schema with alert_count - for list view (performance optimized)."""

    id: UUID
    primary_alert_id: UUID | None = None
    affected_labels: dict[str, str] | None = None
    started_at: datetime
    resolved_at: datetime | None = None
    rca_completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    alert_count: int = Field(default=0, description="Number of correlated alerts")

    model_config = {"from_attributes": True}


class IncidentListResponse(BaseModel):
    """Paginated list of incidents."""

    incidents: list[IncidentSummary]
    total: int
    limit: int
    offset: int


# ============================================================================
# RCA Report Schemas
# ============================================================================


class TimelineEvent(BaseModel):
    """Timeline event in RCA report."""

    timestamp: datetime
    event: str
    source: str = Field(..., description="Source: alert, log, or metric")
    details: dict | None = None


class LogEvidence(BaseModel):
    """Log evidence in RCA report."""

    timestamp: datetime
    message: str
    source: str = "loki"
    labels: dict[str, str] = Field(default_factory=dict)


class MetricEvidence(BaseModel):
    """Metric evidence in RCA report."""

    name: str
    value: float
    timestamp: datetime
    labels: dict[str, str] = Field(default_factory=dict)


class Evidence(BaseModel):
    """Evidence container for RCA report."""

    logs: list[LogEvidence] = Field(default_factory=list)
    metrics: list[MetricEvidence] = Field(default_factory=list)


class RemediationStep(BaseModel):
    """Remediation step in RCA report."""

    priority: RemediationPriority
    action: str
    command: str | None = None
    description: str | None = None
    risk: RiskLevel = RiskLevel.LOW


class AnalysisMetadata(BaseModel):
    """Analysis metadata for RCA report."""

    model: str = Field(..., description="LLM model used")
    tokens_used: int = Field(default=0, description="Total tokens used")
    duration_seconds: float = Field(default=0.0, description="Analysis duration")
    tool_calls: int = Field(default=0, description="Number of tool calls made")


class RCAReportBase(BaseModel):
    """Base RCA report schema."""

    root_cause: str
    confidence_score: int = Field(..., ge=0, le=100)
    summary: str
    timeline: list[TimelineEvent] = Field(default_factory=list)
    evidence: Evidence = Field(default_factory=Evidence)
    remediation_steps: list[RemediationStep] = Field(default_factory=list)


class RCAReportCreate(RCAReportBase):
    """Schema for creating an RCA report."""

    incident_id: UUID


class RCAReportResponse(RCAReportBase):
    """RCA report response schema."""

    id: UUID
    incident_id: UUID
    status: RCAReportStatus
    error_message: str | None = None
    analysis_metadata: AnalysisMetadata | None = None
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RCAReportSummary(BaseModel):
    """Summary of RCA report for list view."""

    id: UUID
    incident_id: UUID
    root_cause: str
    confidence_score: int
    status: RCAReportStatus
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class RCAReportListResponse(BaseModel):
    """Paginated list of RCA reports."""

    reports: list[RCAReportSummary]
    total: int
    limit: int
    offset: int


# ============================================================================
# Correlation Schemas
# ============================================================================


class ManualCorrelationRequest(BaseModel):
    """Request to manually correlate alerts with an incident."""

    alert_ids: list[UUID] = Field(..., description="Alert IDs to correlate with the incident")


class ManualCorrelationResponse(BaseModel):
    """Response for manual correlation."""

    success: bool
    incident_id: UUID
    alerts_correlated: int
    message: str
