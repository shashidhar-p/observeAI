"""Alert SQLAlchemy model."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.incident import Incident


class AlertSeverity(str, enum.Enum):
    """Alert severity levels."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertStatus(str, enum.Enum):
    """Alert status."""

    FIRING = "firing"
    RESOLVED = "resolved"


class Alert(Base, UUIDMixin, TimestampMixin):
    """
    Alert model representing an incoming notification from Alert Manager.

    Attributes:
        id: Internal unique identifier (UUID)
        fingerprint: Alert Manager fingerprint for deduplication
        alertname: Name of the alert rule
        severity: Alert severity level (critical, warning, info)
        status: Alert status (firing, resolved)
        labels: Key-value pairs (service, pod, namespace, etc.)
        annotations: Description, runbook_url, summary
        starts_at: When the alert started firing
        ends_at: When the alert resolved (null if still firing)
        generator_url: Link to the alert source
        incident_id: Associated incident (null if not yet correlated)
        received_at: When system received the alert
    """

    __tablename__ = "alerts"

    fingerprint: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    alertname: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(
            AlertSeverity,
            name="alertseverity",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    status: Mapped[AlertStatus] = mapped_column(
        Enum(
            AlertStatus,
            name="alertstatus",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    labels: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    annotations: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    generator_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    incident_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    incident: Mapped[Incident | None] = relationship(
        "Incident",
        back_populates="alerts",
        foreign_keys=[incident_id],
    )

    __table_args__ = (
        Index("idx_alert_starts_at", "starts_at"),
        Index("idx_alert_labels_service", labels["service"].astext),
    )

    def __repr__(self) -> str:
        return f"<Alert {self.alertname} ({self.severity.value}) - {self.status.value}>"
