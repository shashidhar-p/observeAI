"""Report generation tool for the RCA agent."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


def _parse_json_arg(value: Any, arg_name: str) -> Any:
    """Parse an argument that might be a JSON string from Ollama.

    Ollama sometimes sends tool arguments as JSON strings instead of
    proper objects/arrays. This helper handles both cases.
    """
    if value is None:
        return None

    if isinstance(value, str):
        # Try to parse as JSON
        try:
            parsed = json.loads(value)
            logger.debug(f"Parsed {arg_name} from JSON string")
            return parsed
        except json.JSONDecodeError:
            # Not valid JSON, might be a plain string description
            logger.warning(f"{arg_name} is a non-JSON string: {value[:100]}...")
            return None

    return value


def _infer_command_from_action(action: str, root_cause: str) -> str | None:
    """
    Infer a shell command from the action text when the LLM doesn't provide one.

    This is a fallback to ensure remediation steps have actionable commands.
    """
    action_lower = action.lower()
    root_cause_lower = root_cause.lower()
    combined = f"{action_lower} {root_cause_lower}"

    # Network interface patterns
    if any(x in combined for x in ["interface", "network", "eth", "veth", "ens", "enp"]):
        # Extract device name
        import re
        device_match = re.search(r'(eth\d+|veth\d+|ens\d+\w*|enp\d+s\d+\w*|dummy\d+)', combined)
        device = device_match.group(1) if device_match else "eth0"

        if any(x in action_lower for x in ["bring up", "set up", "restore", "enable", "fix"]):
            return f"sudo ip link set {device} up"
        if any(x in action_lower for x in ["verify", "check", "status", "investigate"]):
            return f"ip link show {device}"
        if any(x in action_lower for x in ["ping", "connectivity", "network"]):
            return "ping -c 3 $(ip route | grep default | awk '{print $3}')"
        if any(x in action_lower for x in ["dmesg", "kernel", "log"]):
            return f"dmesg | tail -50 | grep -i {device}"
        # Default for network issues
        return f"ip link show {device}"

    # Disk space patterns
    if any(x in combined for x in ["disk", "space", "storage", "full"]):
        if any(x in action_lower for x in ["check", "verify", "status"]):
            return "df -h"
        if any(x in action_lower for x in ["clean", "clear", "remove", "delete"]):
            return "sudo find /var/log -name '*.gz' -mtime +7 -delete"
        return "df -h"

    # Memory patterns
    if any(x in combined for x in ["memory", "oom", "ram"]):
        if any(x in action_lower for x in ["check", "verify", "status"]):
            return "free -m"
        return "free -m && top -bn1 | head -20"

    # CPU patterns
    if any(x in combined for x in ["cpu", "load", "process"]):
        if any(x in action_lower for x in ["check", "verify", "status"]):
            return "top -bn1 | head -20"
        return "top -bn1 | head -20"

    # Service/systemd patterns
    if any(x in combined for x in ["service", "systemd", "daemon"]):
        # Try to extract service name
        import re
        service_match = re.search(r'(\w+[-\w]*(?:\.service)?)', combined)
        service = service_match.group(1) if service_match else "service-name"
        service = service.replace(".service", "")

        if any(x in action_lower for x in ["restart"]):
            return f"sudo systemctl restart {service}"
        if any(x in action_lower for x in ["check", "status", "verify"]):
            return f"systemctl status {service}"
        if any(x in action_lower for x in ["start"]):
            return f"sudo systemctl start {service}"
        return f"systemctl status {service}"

    # Docker/container patterns
    if any(x in combined for x in ["container", "docker", "pod"]):
        if any(x in action_lower for x in ["restart"]):
            return "docker ps -a && docker restart <container_id>"
        if any(x in action_lower for x in ["check", "status", "verify"]):
            return "docker ps -a"
        if any(x in action_lower for x in ["logs"]):
            return "docker logs --tail 100 <container_id>"
        return "docker ps -a"

    # Kubernetes patterns
    if any(x in combined for x in ["kubernetes", "kubectl", "k8s", "deployment", "pod"]):
        if any(x in action_lower for x in ["restart", "rollout"]):
            return "kubectl rollout restart deployment/<deployment-name>"
        if any(x in action_lower for x in ["scale"]):
            return "kubectl scale deployment/<deployment-name> --replicas=3"
        if any(x in action_lower for x in ["check", "status", "verify"]):
            return "kubectl get pods"
        return "kubectl get pods"

    # Generic investigation patterns
    if any(x in action_lower for x in ["investigate", "review", "check", "verify"]):
        return "journalctl -xe --no-pager | tail -100"

    # Generic log check
    if any(x in action_lower for x in ["log", "error"]):
        return "journalctl -xe --no-pager | tail -50"

    # No pattern matched - return None (no command)
    return None


# Pydantic models for structured output
class TimelineEvent(BaseModel):
    """A single event in the incident timeline."""

    timestamp: str = Field(..., description="ISO 8601 timestamp")
    event: str = Field(..., description="Description of what happened")
    source: str = Field(..., description="Source: alert, log, or metric")
    details: dict | None = Field(default=None, description="Additional details")


class LogEvidence(BaseModel):
    """Log-based evidence for the RCA."""

    timestamp: str = Field(..., description="ISO 8601 timestamp")
    message: str = Field(..., description="Log message content")
    source: str = Field(default="loki", description="Log source")
    labels: dict[str, str] = Field(default_factory=dict, description="Log labels")


class MetricEvidence(BaseModel):
    """Metric-based evidence for the RCA."""

    name: str = Field(..., description="Metric name")
    value: float = Field(..., description="Metric value")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    labels: dict[str, str] = Field(default_factory=dict, description="Metric labels")


class Evidence(BaseModel):
    """Container for all evidence supporting the RCA."""

    logs: list[LogEvidence] = Field(default_factory=list)
    metrics: list[MetricEvidence] = Field(default_factory=list)


class RemediationStep(BaseModel):
    """A remediation step for resolving the issue."""

    priority: str = Field(..., description="Priority: 'immediate' or 'long_term'")
    action: str = Field(..., description="Action to take")
    command: str | None = Field(default=None, description="Optional command to run")
    description: str | None = Field(default=None, description="Detailed description")
    risk: str = Field(default="low", description="Risk level: 'low', 'medium', 'high'")
    category: str | None = Field(
        default=None,
        description="Category: 'restart', 'scale', 'config', 'cleanup', 'rollback', 'investigate'"
    )
    estimated_impact: str | None = Field(
        default=None,
        description="Expected impact: 'service_restart', 'brief_downtime', 'no_downtime', 'data_loss_risk'"
    )
    requires_approval: bool = Field(
        default=False,
        description="Whether this action requires manual approval before execution"
    )
    automation_ready: bool = Field(
        default=False,
        description="Whether this step can be automated or requires manual intervention"
    )

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v not in ("immediate", "long_term"):
            raise ValueError("priority must be 'immediate' or 'long_term'")
        return v

    @field_validator("risk")
    @classmethod
    def validate_risk(cls, v: str) -> str:
        if v not in ("low", "medium", "high"):
            raise ValueError("risk must be 'low', 'medium', or 'high'")
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str | None) -> str | None:
        if v is None:
            return v
        valid = ("restart", "scale", "config", "cleanup", "rollback", "investigate", "other")
        if v not in valid:
            return "other"
        return v


class RCAReportOutput(BaseModel):
    """Complete RCA report structure."""

    root_cause: str = Field(..., description="Identified root cause")
    confidence_score: int = Field(..., ge=0, le=100, description="Confidence 0-100%")
    summary: str = Field(..., description="Executive summary of findings")
    timeline: list[TimelineEvent] = Field(default_factory=list)
    evidence: Evidence = Field(default_factory=Evidence)
    remediation_steps: list[RemediationStep] = Field(default_factory=list)


# Tool definition for Claude
GENERATE_REPORT_TOOL = {
    "name": "generate_report",
    "description": (
        "Generate the final RCA report with root cause, confidence score, evidence, "
        "and remediation steps. Call this tool when you have gathered enough information "
        "to make a determination about the root cause."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "root_cause": {
                "type": "string",
                "description": (
                    "Clear description of the identified root cause based on the evidence. "
                    "Be specific about what failed and why. Must be derived from the actual "
                    "logs and metrics you queried, not from examples."
                ),
            },
            "confidence_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": (
                    "Confidence level in the root cause analysis (0-100%). "
                    "100% = definitive evidence, 75% = strong indicators, "
                    "50% = likely but incomplete evidence, <50% = uncertain"
                ),
            },
            "summary": {
                "type": "string",
                "description": (
                    "Executive summary (2-3 sentences) for quick understanding. "
                    "Include: what happened, impact, and resolution status."
                ),
            },
            "timeline": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "timestamp": {"type": "string", "description": "ISO 8601 timestamp"},
                        "event": {"type": "string", "description": "What happened"},
                        "source": {
                            "type": "string",
                            "enum": ["alert", "log", "metric"],
                            "description": "Event source",
                        },
                    },
                    "required": ["timestamp", "event", "source"],
                },
                "description": "Chronological sequence of events leading to the incident",
            },
            "evidence": {
                "type": "object",
                "properties": {
                    "logs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "timestamp": {"type": "string"},
                                "message": {"type": "string"},
                                "labels": {"type": "object"},
                            },
                            "required": ["timestamp", "message"],
                        },
                        "description": "Key log entries supporting the analysis",
                    },
                    "metrics": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "value": {"type": "number"},
                                "timestamp": {"type": "string"},
                                "labels": {"type": "object"},
                            },
                            "required": ["name", "value", "timestamp"],
                        },
                        "description": "Key metrics supporting the analysis",
                    },
                },
                "description": "Evidence from logs and metrics",
            },
            "remediation_steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "priority": {
                            "type": "string",
                            "enum": ["immediate", "long_term"],
                            "description": "Action urgency: 'immediate' for actions to take now, 'long_term' for preventive measures",
                        },
                        "action": {
                            "type": "string",
                            "description": "Concise action title (e.g., 'Restart the payment-api pod')",
                        },
                        "command": {
                            "type": "string",
                            "description": "Specific command to run (e.g., 'kubectl rollout restart deployment/payment-api -n prod')",
                        },
                        "description": {
                            "type": "string",
                            "description": "Detailed explanation of why this action is needed and expected outcome",
                        },
                        "risk": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                            "description": "Risk level: 'low' (safe), 'medium' (brief impact), 'high' (potential data loss/downtime)",
                        },
                        "category": {
                            "type": "string",
                            "enum": ["restart", "scale", "config", "cleanup", "rollback", "investigate", "other"],
                            "description": "Action category for grouping similar actions",
                        },
                        "estimated_impact": {
                            "type": "string",
                            "enum": ["no_downtime", "brief_downtime", "service_restart", "data_loss_risk"],
                            "description": "Expected impact on service availability",
                        },
                        "requires_approval": {
                            "type": "boolean",
                            "description": "Whether this action requires manual approval (true for high-risk actions)",
                        },
                        "automation_ready": {
                            "type": "boolean",
                            "description": "Whether this step can be automated (false if requires human judgment)",
                        },
                    },
                    "required": ["priority", "action"],
                },
                "description": "Steps to resolve the issue and prevent recurrence",
            },
        },
        "required": ["root_cause", "confidence_score", "summary", "remediation_steps"],
    },
}


def execute_generate_report(
    root_cause: str,
    confidence_score: int,
    summary: str,
    timeline: list[dict] | str | None = None,
    evidence: dict | str | None = None,
    remediation_steps: list[dict] | str | None = None,
) -> dict[str, Any]:
    """
    Validate and format the RCA report.

    Args:
        root_cause: Identified root cause description
        confidence_score: Confidence level (0-100)
        summary: Executive summary
        timeline: List of timeline events (may be JSON string from Ollama)
        evidence: Evidence container with logs and metrics (may be JSON string)
        remediation_steps: List of remediation steps (may be JSON string)

    Returns:
        dict: Validated and formatted report data
    """
    try:
        # Parse arguments that might be JSON strings (Ollama compatibility)
        timeline = _parse_json_arg(timeline, "timeline")
        evidence = _parse_json_arg(evidence, "evidence")
        remediation_steps = _parse_json_arg(remediation_steps, "remediation_steps")

        # Ensure timeline is a list
        if timeline is not None and not isinstance(timeline, list):
            logger.warning(f"timeline is not a list: {type(timeline)}, wrapping")
            timeline = [timeline] if isinstance(timeline, dict) else None

        # Ensure evidence is a dict
        if evidence is not None and not isinstance(evidence, dict):
            logger.warning(f"evidence is not a dict: {type(evidence)}, ignoring")
            evidence = None

        # Ensure remediation_steps is a list
        if remediation_steps is not None and not isinstance(remediation_steps, list):
            logger.warning(f"remediation_steps is not a list: {type(remediation_steps)}")
            if isinstance(remediation_steps, dict):
                remediation_steps = [remediation_steps]
            elif isinstance(remediation_steps, str):
                # Try to create a simple step from the string
                remediation_steps = [{"priority": "immediate", "action": remediation_steps}]
            else:
                remediation_steps = None

        # Build evidence object
        evidence_obj = Evidence()
        if evidence:
            if "logs" in evidence:
                logs_list = evidence.get("logs", [])
                if isinstance(logs_list, list):
                    for log in logs_list:
                        if isinstance(log, dict):
                            evidence_obj.logs.append(
                                LogEvidence(
                                    timestamp=log.get("timestamp", datetime.now(UTC).isoformat()),
                                    message=log.get("message", ""),
                                    source=log.get("source", "loki"),
                                    labels=log.get("labels", {}),
                                )
                            )
                        elif isinstance(log, str):
                            # Plain string log entry
                            evidence_obj.logs.append(
                                LogEvidence(
                                    timestamp=datetime.now(UTC).isoformat(),
                                    message=log,
                                    source="loki",
                                    labels={},
                                )
                            )
            if "metrics" in evidence:
                metrics_list = evidence.get("metrics", [])
                if isinstance(metrics_list, list):
                    for metric in metrics_list:
                        if isinstance(metric, dict):
                            evidence_obj.metrics.append(
                                MetricEvidence(
                                    name=metric.get("name", "unknown"),
                                    value=float(metric.get("value", 0)),
                                    timestamp=metric.get(
                                        "timestamp", datetime.now(UTC).isoformat()
                                    ),
                                    labels=metric.get("labels", {}),
                                )
                            )

        # Build timeline
        timeline_events = []
        if timeline:
            for event in timeline:
                if isinstance(event, dict):
                    timeline_events.append(
                        TimelineEvent(
                            timestamp=event.get("timestamp", datetime.now(UTC).isoformat()),
                            event=event.get("event", ""),
                            source=event.get("source", "alert"),
                            details=event.get("details"),
                        )
                    )
                elif isinstance(event, str):
                    # Plain string event
                    timeline_events.append(
                        TimelineEvent(
                            timestamp=datetime.now(UTC).isoformat(),
                            event=event,
                            source="alert",
                            details=None,
                        )
                    )

        # Build remediation steps
        steps = []
        if remediation_steps:
            for step in remediation_steps:
                if isinstance(step, dict):
                    action = step.get("action", "")
                    command = step.get("command")

                    # If command is missing, try to infer from action/context
                    if not command:
                        command = _infer_command_from_action(action, root_cause)

                    steps.append(
                        RemediationStep(
                            priority=step.get("priority", "immediate"),
                            action=action,
                            command=command,
                            description=step.get("description"),
                            risk=step.get("risk", "low"),
                            category=step.get("category"),
                            estimated_impact=step.get("estimated_impact"),
                            requires_approval=step.get("requires_approval", False),
                            automation_ready=step.get("automation_ready", False),
                        )
                    )
                elif isinstance(step, str):
                    # Plain string step - try to infer command
                    command = _infer_command_from_action(step, root_cause)
                    steps.append(
                        RemediationStep(
                            priority="immediate",
                            action=step,
                            command=command,
                            description=None,
                            risk="low",
                            category=None,
                            estimated_impact=None,
                            requires_approval=False,
                            automation_ready=False,
                        )
                    )

        # Create and validate full report
        report = RCAReportOutput(
            root_cause=root_cause,
            confidence_score=confidence_score,
            summary=summary,
            timeline=timeline_events,
            evidence=evidence_obj,
            remediation_steps=steps,
        )

        return {
            "success": True,
            "report": report.model_dump(),
        }

    except Exception as e:
        logger.exception(f"Report generation failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }
