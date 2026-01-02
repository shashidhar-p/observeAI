"""RCA Report CRUD service."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models import Incident, RCAReport, RCAReportStatus

logger = logging.getLogger(__name__)


class ReportService:
    """Service for RCA Report CRUD operations."""

    def __init__(self, session: AsyncSession):
        """Initialize the report service."""
        self.session = session

    async def create(
        self,
        incident_id: UUID,
        root_cause: str = "Analysis pending",
        confidence_score: int = 0,
        summary: str = "Analysis in progress",
        timeline: list | None = None,
        evidence: dict | None = None,
        remediation_steps: list | None = None,
        status: RCAReportStatus = RCAReportStatus.PENDING,
    ) -> RCAReport:
        """Create a new RCA report."""
        report = RCAReport(
            incident_id=incident_id,
            root_cause=root_cause,
            confidence_score=confidence_score,
            summary=summary,
            timeline=timeline or [],
            evidence=evidence or {"logs": [], "metrics": []},
            remediation_steps=remediation_steps or [],
            status=status,
            started_at=datetime.utcnow(),
        )
        self.session.add(report)
        await self.session.flush()
        return report

    async def get(self, report_id: UUID) -> RCAReport | None:
        """Get a report by ID."""
        return await self.session.get(RCAReport, report_id)

    async def get_by_incident(self, incident_id: UUID) -> RCAReport | None:
        """Get the report for an incident."""
        result = await self.session.execute(
            select(RCAReport).where(RCAReport.incident_id == incident_id)
        )
        return result.scalar_one_or_none()

    async def get_with_incident(self, report_id: UUID) -> RCAReport | None:
        """Get a report with its incident loaded."""
        result = await self.session.execute(
            select(RCAReport)
            .options(selectinload(RCAReport.incident))
            .where(RCAReport.id == report_id)
        )
        return result.scalar_one_or_none()

    async def list_reports(
        self,
        status: RCAReportStatus | None = None,
        service: str | None = None,
        severity: str | None = None,
        min_confidence: int | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RCAReport], int]:
        """
        List reports with optional filtering.

        Returns:
            tuple: (list of reports, total count)
        """
        query = select(RCAReport).join(Incident)

        # Apply filters
        if status:
            query = query.where(RCAReport.status == status)
        if min_confidence is not None:
            query = query.where(RCAReport.confidence_score >= min_confidence)
        if service:
            query = query.where(Incident.affected_services.contains([service]))
        if severity:
            query = query.where(Incident.severity == severity)
        if since:
            query = query.where(RCAReport.completed_at >= since)
        if until:
            query = query.where(RCAReport.completed_at <= until)

        # Get total count
        from sqlalchemy import func
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar_one()

        # Apply pagination and ordering
        query = query.order_by(RCAReport.created_at.desc()).offset(offset).limit(limit)

        result = await self.session.execute(query)
        reports = result.scalars().all()

        return list(reports), total

    async def update_from_analysis(
        self,
        report_id: UUID,
        root_cause: str,
        confidence_score: int,
        summary: str,
        timeline: list,
        evidence: dict,
        remediation_steps: list,
        analysis_metadata: dict | None = None,
    ) -> RCAReport | None:
        """Update a report with analysis results."""
        report = await self.get(report_id)
        if report:
            report.root_cause = root_cause
            report.confidence_score = confidence_score
            report.summary = summary
            report.timeline = timeline
            report.evidence = evidence
            report.remediation_steps = remediation_steps
            report.analysis_metadata = analysis_metadata
            report.status = RCAReportStatus.COMPLETE
            report.completed_at = datetime.utcnow()
            await self.session.flush()
        return report

    async def mark_failed(
        self,
        report_id: UUID,
        error_message: str,
        analysis_metadata: dict | None = None,
    ) -> RCAReport | None:
        """Mark a report as failed."""
        report = await self.get(report_id)
        if report:
            report.status = RCAReportStatus.FAILED
            report.error_message = error_message
            report.analysis_metadata = analysis_metadata
            report.completed_at = datetime.utcnow()
            await self.session.flush()
        return report

    async def delete(self, report_id: UUID) -> bool:
        """Delete a report."""
        report = await self.get(report_id)
        if report:
            await self.session.delete(report)
            await self.session.flush()
            return True
        return False

    def format_as_markdown(self, report: RCAReport) -> str:
        """Format a report as Markdown."""
        lines = [
            "# RCA Report",
            "",
            f"**Report ID**: {report.id}",
            f"**Status**: {report.status.value}",
            f"**Confidence**: {report.confidence_score}%",
            f"**Created**: {report.created_at.isoformat()}",
            "",
            "## Summary",
            "",
            report.summary,
            "",
            "## Root Cause",
            "",
            report.root_cause,
            "",
        ]

        if report.timeline:
            lines.extend([
                "## Timeline",
                "",
            ])
            for event in report.timeline:
                ts = event.get("timestamp", "Unknown")
                desc = event.get("event", "Unknown event")
                source = event.get("source", "unknown")
                lines.append(f"- **{ts}** [{source}]: {desc}")
            lines.append("")

        if report.evidence:
            logs = report.evidence.get("logs", [])
            metrics = report.evidence.get("metrics", [])

            if logs:
                lines.extend([
                    "## Log Evidence",
                    "",
                ])
                for log in logs[:10]:  # Limit to 10 entries
                    ts = log.get("timestamp", "Unknown")
                    msg = log.get("message", "")[:200]
                    lines.append(f"- `{ts}`: {msg}")
                lines.append("")

            if metrics:
                lines.extend([
                    "## Metric Evidence",
                    "",
                ])
                for metric in metrics[:10]:
                    name = metric.get("name", "Unknown")
                    value = metric.get("value", "N/A")
                    ts = metric.get("timestamp", "Unknown")
                    lines.append(f"- **{name}**: {value} at {ts}")
                lines.append("")

        if report.remediation_steps:
            lines.extend([
                "## Remediation Steps",
                "",
            ])
            for i, step in enumerate(report.remediation_steps, 1):
                priority = step.get("priority", "unknown").upper()
                action = step.get("action", "No action specified")
                risk = step.get("risk", "unknown")
                lines.append(f"{i}. **[{priority}]** {action} (Risk: {risk})")

                if step.get("command"):
                    lines.append("   ```")
                    lines.append(f"   {step['command']}")
                    lines.append("   ```")

                if step.get("description"):
                    lines.append(f"   {step['description']}")

                lines.append("")

        return "\n".join(lines)
