"""RCA Report SQLAlchemy model."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.incident import Incident


class RCAReportStatus(str, enum.Enum):
    """RCA report status."""

    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"


class RCAReport(Base, UUIDMixin, TimestampMixin):
    """
    RCA Report model containing root cause analysis output.

    Attributes:
        id: Unique report identifier (UUID)
        incident_id: One report per incident
        root_cause: Identified root cause description
        confidence_score: Confidence in root cause (0-100%)
        summary: Executive summary of findings
        timeline: Chronological event sequence (JSONB)
        evidence: Supporting logs and metrics (JSONB)
        remediation_steps: Array of remediation suggestions (JSONB)
        analysis_metadata: LLM tokens used, duration, model version (JSONB)
        status: Report status (pending, complete, failed)
        error_message: Error details if status is failed
        started_at: When analysis began
        completed_at: When analysis finished
    """

    __tablename__ = "rca_reports"

    incident_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    root_cause: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    confidence_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    timeline: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    evidence: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    remediation_steps: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    analysis_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    status: Mapped[RCAReportStatus] = mapped_column(
        Enum(
            RCAReportStatus,
            name="rcareportstatus",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=RCAReportStatus.PENDING,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    incident: Mapped[Incident] = relationship(
        "Incident",
        back_populates="rca_report",
    )

    __table_args__ = (
        Index("idx_rca_status", "status"),
        Index("idx_rca_completed_at", "completed_at"),
    )

    def __repr__(self) -> str:
        return f"<RCAReport {self.id} ({self.status.value}) - {self.confidence_score}% confidence>"
