"""Incident SQLAlchemy model."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.alert import Alert
    from src.models.rca_report import RCAReport


class IncidentStatus(str, enum.Enum):
    """Incident status."""

    OPEN = "open"
    ANALYZING = "analyzing"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentSeverity(str, enum.Enum):
    """Incident severity (derived from alerts)."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class Incident(Base, UUIDMixin, TimestampMixin):
    """
    Incident model representing a correlated group of related alerts.

    Attributes:
        id: Unique incident identifier (UUID)
        title: Human-readable incident title
        status: Incident status (open, analyzing, resolved, closed)
        severity: Highest severity from correlated alerts
        primary_alert_id: The root cause alert
        correlation_reason: Why alerts were grouped
        affected_services: List of affected service names
        affected_labels: Common labels across alerts
        started_at: Earliest alert start time
        resolved_at: When incident was resolved
    """

    __tablename__ = "incidents"

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(
            IncidentStatus,
            name="incidentstatus",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=IncidentStatus.OPEN,
    )
    severity: Mapped[IncidentSeverity] = mapped_column(
        Enum(
            IncidentSeverity,
            name="incidentseverity",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    primary_alert_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    correlation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    affected_services: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
    )
    affected_labels: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    rca_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    alerts: Mapped[list[Alert]] = relationship(
        "Alert",
        back_populates="incident",
        foreign_keys="Alert.incident_id",
    )
    primary_alert: Mapped[Alert | None] = relationship(
        "Alert",
        foreign_keys=[primary_alert_id],
        post_update=True,
    )
    rca_report: Mapped[RCAReport | None] = relationship(
        "RCAReport",
        back_populates="incident",
        uselist=False,
    )

    __table_args__ = (
        Index("idx_incident_status", "status"),
        Index("idx_incident_started_at", "started_at"),
        Index("idx_incident_severity", "severity"),
    )

    def __repr__(self) -> str:
        return f"<Incident {self.title[:50]} ({self.status.value})>"
