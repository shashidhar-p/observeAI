"""Initial schema with alerts, incidents, and rca_reports tables.

Revision ID: 001
Revises:
Create Date: 2025-12-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create enums
    alertseverity = postgresql.ENUM(
        "critical", "warning", "info", name="alertseverity", create_type=False
    )
    alertseverity.create(op.get_bind(), checkfirst=True)

    alertstatus = postgresql.ENUM("firing", "resolved", name="alertstatus", create_type=False)
    alertstatus.create(op.get_bind(), checkfirst=True)

    incidentstatus = postgresql.ENUM(
        "open", "analyzing", "resolved", "closed", name="incidentstatus", create_type=False
    )
    incidentstatus.create(op.get_bind(), checkfirst=True)

    incidentseverity = postgresql.ENUM(
        "critical", "warning", "info", name="incidentseverity", create_type=False
    )
    incidentseverity.create(op.get_bind(), checkfirst=True)

    rcareportstatus = postgresql.ENUM(
        "pending", "complete", "failed", name="rcareportstatus", create_type=False
    )
    rcareportstatus.create(op.get_bind(), checkfirst=True)

    # Create incidents table first (alerts reference it)
    op.create_table(
        "incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "open", "analyzing", "resolved", "closed", name="incidentstatus", create_type=False
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            postgresql.ENUM(
                "critical", "warning", "info", name="incidentseverity", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("primary_alert_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("correlation_reason", sa.Text(), nullable=True),
        sa.Column("affected_services", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("affected_labels", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_incident_severity", "incidents", ["severity"], unique=False)
    op.create_index("idx_incident_started_at", "incidents", ["started_at"], unique=False)
    op.create_index("idx_incident_status", "incidents", ["status"], unique=False)

    # Create alerts table
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("alertname", sa.String(length=255), nullable=False),
        sa.Column(
            "severity",
            postgresql.ENUM("critical", "warning", "info", name="alertseverity", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM("firing", "resolved", name="alertstatus", create_type=False),
            nullable=False,
        ),
        sa.Column("labels", postgresql.JSONB(), nullable=False),
        sa.Column("annotations", postgresql.JSONB(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generator_url", sa.Text(), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_alert_starts_at", "alerts", ["starts_at"], unique=False)
    op.create_index(op.f("ix_alerts_fingerprint"), "alerts", ["fingerprint"], unique=True)
    op.create_index(op.f("ix_alerts_incident_id"), "alerts", ["incident_id"], unique=False)
    # Index on JSONB field for service label
    op.execute("CREATE INDEX idx_alert_labels_service ON alerts ((labels->>'service'))")

    # Add foreign key from incidents.primary_alert_id to alerts.id
    op.create_foreign_key(
        "fk_incidents_primary_alert_id",
        "incidents",
        "alerts",
        ["primary_alert_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Create rca_reports table
    op.create_table(
        "rca_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("timeline", postgresql.JSONB(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("remediation_steps", postgresql.JSONB(), nullable=False),
        sa.Column("analysis_metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("pending", "complete", "failed", name="rcareportstatus", create_type=False),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_rca_completed_at", "rca_reports", ["completed_at"], unique=False)
    op.create_index("idx_rca_status", "rca_reports", ["status"], unique=False)
    op.create_index(op.f("ix_rca_reports_incident_id"), "rca_reports", ["incident_id"], unique=True)


def downgrade() -> None:
    # Drop rca_reports table
    op.drop_index(op.f("ix_rca_reports_incident_id"), table_name="rca_reports")
    op.drop_index("idx_rca_status", table_name="rca_reports")
    op.drop_index("idx_rca_completed_at", table_name="rca_reports")
    op.drop_table("rca_reports")

    # Drop foreign key from incidents to alerts
    op.drop_constraint("fk_incidents_primary_alert_id", "incidents", type_="foreignkey")

    # Drop alerts table
    op.execute("DROP INDEX IF EXISTS idx_alert_labels_service")
    op.drop_index(op.f("ix_alerts_incident_id"), table_name="alerts")
    op.drop_index(op.f("ix_alerts_fingerprint"), table_name="alerts")
    op.drop_index("idx_alert_starts_at", table_name="alerts")
    op.drop_table("alerts")

    # Drop incidents table
    op.drop_index("idx_incident_status", table_name="incidents")
    op.drop_index("idx_incident_started_at", table_name="incidents")
    op.drop_index("idx_incident_severity", table_name="incidents")
    op.drop_table("incidents")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS rcareportstatus")
    op.execute("DROP TYPE IF EXISTS incidentseverity")
    op.execute("DROP TYPE IF EXISTS incidentstatus")
    op.execute("DROP TYPE IF EXISTS alertstatus")
    op.execute("DROP TYPE IF EXISTS alertseverity")
