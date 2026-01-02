"""RCA Agent using pluggable LLM providers with native tool use."""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from src.config import get_settings
from src.models import Alert, Incident
from src.services.llm import LLMProvider, create_llm_provider
from src.tools.generate_report import (
    GENERATE_REPORT_TOOL,
    execute_generate_report,
)
from src.tools.query_cortex import QUERY_CORTEX_TOOL, PromQLQueryBuilder, execute_query_cortex
from src.tools.query_loki import QUERY_LOKI_TOOL, LogQLQueryBuilder, execute_query_loki

logger = logging.getLogger(__name__)
settings = get_settings()

# System prompt for RCA analysis
RCA_SYSTEM_PROMPT = r"""You are an expert Site Reliability Engineer (SRE) and Root Cause Analysis specialist. Your task is to analyze alerts from infrastructure monitoring systems and determine the root cause of issues.

## Your Workflow

1. **Understand the Alert(s)**: Analyze alert details including severity, labels, annotations, and timing.
   - For multiple correlated alerts, identify the chronological sequence
   - Pay attention to which alert fired first - it's often closest to root cause

2. **Gather Evidence**: Use the available tools to query logs (Loki) and metrics (Cortex) related to the alert.
   - Query logs for error messages, exceptions, and relevant events
   - Query metrics for resource utilization, error rates, and performance indicators
   - Focus on the time window around the alert (typically 15 minutes before to 5 minutes after)

3. **Analyze Patterns**: Look for:
   - Error patterns in logs (exceptions, failures, timeouts)
   - Resource exhaustion (CPU, memory, disk, network)
   - Cascading failures (one failure causing others)
   - Configuration changes or deployments
   - External dependency issues

4. **Determine Root Cause**: Based on evidence:
   - Identify the primary cause vs symptoms
   - Assign a confidence score (0-100%)
   - Document supporting evidence

5. **Generate Report**: Call the generate_report tool with:
   - Clear root cause description
   - Confidence score with justification
   - Timeline of events
   - Supporting evidence (key logs and metrics)
   - Actionable remediation steps (both immediate and long-term)

## Multi-Alert Correlation Analysis

When analyzing multiple correlated alerts, follow this enhanced workflow:

### Causal Chain Identification

1. **Order alerts chronologically** - The first alert is often the root cause
2. **Identify the causal chain** - Map how one failure triggered subsequent failures
3. **Distinguish root cause from symptoms**:
   - ROOT CAUSE indicators: disk full, OOM killer, resource quota exceeded, configuration error
   - SYMPTOM indicators: health check failed, service unavailable, high latency, timeout

### Common Causal Patterns

- **Resource Exhaustion Chain**: DiskFull → LogWriteFailed → ServiceCrash → HealthCheckFailed
- **Memory Pressure Chain**: MemoryPressure → OOMKilled → PodRestart → ServiceDegraded
- **Network Chain**: NetworkPartition → TimeoutErrors → RetryStorms → CircuitBreakerOpen
- **Dependency Chain**: DatabaseOverload → SlowQueries → APITimeout → UserErrors

### Timeline Construction

For multi-alert incidents, build a detailed timeline showing:
1. Initial trigger event (from logs/metrics)
2. First alert firing
3. Cascading failures
4. Subsequent symptom alerts
5. Impact on services/users

### Report Requirements for Multi-Alert

- **root_cause**: Focus on the PRIMARY cause, not symptoms
- **summary**: Explain the full causal chain concisely
- **timeline**: Include ALL correlated alerts with their relationships
- **remediation_steps**: Address root cause first, then add preventive measures for cascade

## Tool Usage Guidelines

- **query_loki**: Use LogQL to search logs. Start with broad queries, then narrow down.
  - Example: `{service="payment-api"} |= "error"` for error logs
  - Example: `{namespace="production"} |~ "OOM|OutOfMemory"` for memory issues

- **query_cortex**: Use PromQL to query metrics.
  - Example: `100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])))` for CPU
  - Example: `rate(http_requests_total{status=~"5.."}[5m])` for error rates

- **generate_report**: Call this ONCE when you have enough evidence to make a determination.

## Remediation Guidelines

When generating remediation steps, follow these principles:

### ⚠️ MANDATORY: EVERY REMEDIATION STEP REQUIRES A COMMAND ⚠️

THIS IS NON-NEGOTIABLE: Every single remediation step MUST have a `command` field with an actual shell command.
DO NOT skip the command field. DO NOT provide empty commands. DO NOT provide placeholder commands.

For each remediation step, the `command` field MUST contain:
- An actual executable shell command (e.g., `sudo ip link set eth0 up`)
- NOT just a description
- NOT "run the appropriate command"
- NOT an empty string

### Structure for Each Remediation Step

Every remediation step MUST include THREE types of commands when applicable:
1. **Verification Command**: How to verify/diagnose the issue (e.g., `ip a`, `ip link show eth0`)
2. **Fix Command**: How to fix the issue (e.g., `sudo ip link set eth0 up`)
3. **Validation Command**: How to confirm the fix worked (e.g., `ping -c 3 10.0.0.1`)

### Immediate Actions (priority: "immediate")
Actions to take RIGHT NOW to restore service:
1. **Restart**: Pod/service restart, connection pool refresh
2. **Scale**: Horizontal/vertical scaling for resource exhaustion
3. **Rollback**: Revert recent changes if they caused the issue
4. **Cleanup**: Clear disk space, purge queues, close connections

### Long-term Actions (priority: "long_term")
Preventive measures to avoid recurrence:
1. **Config**: Adjust limits, timeouts, thresholds
2. **Monitoring**: Add alerts, dashboards, tracing
3. **Architecture**: Improve retry logic, circuit breakers, caching
4. **Process**: Update runbooks, improve deployment practices

### Remediation Requirements

For EACH remediation step, you MUST provide:
- **action**: Clear, concise action title (e.g., "Bring network interface eth0 back up")
- **command**: REQUIRED - Specific shell command(s) to run (e.g., `sudo ip link set eth0 up`)
- **description**: Step-by-step explanation including:
  1. How to verify the issue (verification command)
  2. How to apply the fix (the command field)
  3. How to validate the fix worked (validation command)
- **risk**: "low" (safe), "medium" (brief impact), "high" (potential data loss)
- **category**: restart, scale, config, cleanup, rollback, or investigate
- **estimated_impact**: no_downtime, brief_downtime, service_restart, data_loss_risk
- **requires_approval**: true for high-risk actions
- **automation_ready**: true if action can be scripted, false if needs human judgment

### Network Interface Remediation Commands

For NetworkInterfaceDown alerts, use these specific commands:

**Step 1: Verify interface is down**
- action: "Verify network interface status"
- command: "ip link show eth0"
- description: "Check interface state. Look for 'state DOWN' in output. Alternative: 'ip a' to see all interfaces."

**Step 2: Bring interface up**
- action: "Bring network interface up"
- command: "sudo ip link set eth0 up"
- description: "This brings the interface back to UP state. Run 'ip link show eth0' to verify it shows 'state UP'."

**Step 3: Verify network connectivity**
- action: "Verify network connectivity restored"
- command: "ping -c 3 <gateway_ip>"
- description: "Confirm connectivity is restored by pinging the default gateway. Use 'ip route | grep default' to find gateway."

**Step 4: Check for underlying cause**
- action: "Investigate root cause"
- command: "dmesg | tail -50 | grep -i eth"
- description: "Check kernel messages for hardware errors, driver issues, or cable problems that caused the interface to go down."

### Common Remediation Patterns

| Issue Type | Verification | Fix Command | Validation |
|------------|--------------|-------------|------------|
| Network Interface Down | `ip link show <dev>` | `sudo ip link set <dev> up` | `ping -c 3 <gateway>` |
| Disk Full | `df -h` | `sudo rm -rf /var/log/*.gz` | `df -h` |
| OOM | `free -m` | `kubectl rollout restart deploy/<name>` | `kubectl get pods` |
| CPU Saturation | `top -bn1 \| head -20` | `kubectl scale deploy/<name> --replicas=3` | `kubectl get pods` |
| Service Down | `systemctl status <svc>` | `sudo systemctl restart <svc>` | `systemctl status <svc>` |
| Container Crash | `docker ps -a` | `docker restart <id>` | `docker ps` |

## Important Notes

- Always provide evidence for your conclusions
- If data is unavailable, note it in the report
- Be specific in remediation steps - include commands when appropriate
- Order remediation steps by priority: immediate actions first
- Assign lower confidence scores when evidence is incomplete
- For high-risk actions, set requires_approval: true
"""


class RCAAgent:
    """
    Unified RCA Agent using pluggable LLM providers with native tool calling.

    This agent analyzes alerts by querying logs and metrics, then generates
    an RCA report with root cause, evidence, and remediation steps.

    Supports multiple LLM backends:
    - Anthropic Claude (cloud)
    - Ollama (local)
    """

    def __init__(self, llm_provider: LLMProvider | None = None):
        """
        Initialize the RCA agent.

        Args:
            llm_provider: Optional LLM provider. If not provided, creates one from settings.
        """
        self.llm = llm_provider or create_llm_provider(settings)
        self.max_iterations = settings.rca_max_iterations
        self.tools = [QUERY_LOKI_TOOL, QUERY_CORTEX_TOOL, GENERATE_REPORT_TOOL]

        # Metrics tracking
        self.total_tokens = 0
        self.tool_calls = 0
        self.start_time: float | None = None

        # Query context - stores correct time range for tool calls
        # This prevents LLM from hallucinating timestamps
        self.query_start_time: str | None = None
        self.query_end_time: str | None = None

        # Build system prompt with expert context
        self.system_prompt = self._build_system_prompt()

        logger.info(f"RCA Agent initialized with {self.llm.name} provider ({self.llm.model})")

    def _build_system_prompt(self) -> str:
        """
        Build the full system prompt, optionally including expert context.

        Priority:
        1. RCA_EXPERT_CONTEXT_FILE - load from file path
        2. RCA_EXPERT_CONTEXT - use inline value
        3. Neither set - use generic SRE prompt only
        """
        expert_context = ""

        # Try loading from file first
        if settings.rca_expert_context_file.strip():
            try:
                with open(settings.rca_expert_context_file.strip()) as f:
                    expert_context = f.read().strip()
                logger.info(f"Loaded RCA expert context from file: {settings.rca_expert_context_file}")
            except Exception as e:
                logger.warning(f"Failed to load expert context file: {e}")

        # Fall back to inline env var
        if not expert_context:
            expert_context = settings.rca_expert_context.strip()
            if expert_context:
                logger.info("Using inline RCA expert context from environment")

        if expert_context:
            return f"{RCA_SYSTEM_PROMPT}\n\n{expert_context}"
        return RCA_SYSTEM_PROMPT

    def _format_alert_for_analysis(self, alert: Alert | dict) -> str:
        """Format alert data for LLM's initial analysis."""
        from datetime import timedelta

        if isinstance(alert, Alert):
            data = {
                "alertname": alert.alertname,
                "severity": alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity),
                "status": alert.status.value if hasattr(alert.status, "value") else str(alert.status),
                "labels": alert.labels,
                "annotations": alert.annotations or {},
                "starts_at": alert.starts_at.isoformat() if alert.starts_at else None,
                "ends_at": alert.ends_at.isoformat() if alert.ends_at else None,
            }
            labels = alert.labels or {}
            alertname = alert.alertname
            alert_time = alert.starts_at
        else:
            data = alert
            labels = data.get("labels", {})
            alertname = data.get("alertname", "Unknown")
            # Parse alert time from string if available
            starts_at = data.get("starts_at")
            if starts_at:
                try:
                    alert_time = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    alert_time = datetime.now(UTC)
            else:
                alert_time = datetime.now(UTC)

        # Calculate recommended query time window
        # Start: 15 minutes before alert, End: current time or 5 minutes after alert
        now = datetime.now(UTC)
        query_start = alert_time - timedelta(minutes=15)
        query_end = max(now, alert_time + timedelta(minutes=5))

        # Format as ISO strings for the LLM to use directly
        query_start_iso = query_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        query_end_iso = query_end.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Store for use in tool calls (to override hallucinated timestamps)
        self.query_start_time = query_start_iso
        self.query_end_time = query_end_iso

        # Generate intelligent query hints
        logql_builder = LogQLQueryBuilder(labels)
        promql_builder = PromQLQueryBuilder(labels)

        logql_hints = logql_builder.get_query_hints(alertname)
        promql_hints = promql_builder.get_query_hints(alertname)

        # Detect potential service dependencies
        dependencies = self._detect_dependencies(labels, alertname)
        dependency_hints = ""
        if dependencies:
            dependency_hints = f"\n\n## Potential Dependencies\n\nConsider querying these related services: {', '.join(dependencies)}"

        return f"""Please analyze the following alert and determine its root cause:

## Alert Details

```json
{json.dumps(data, indent=2, default=str)}
```

## Time Context - USE THESE EXACT TIMESTAMPS

- Alert Start: {data.get('starts_at', 'Unknown')}
- Current Time: {now.isoformat()}
- **Query Start Time (use this)**: {query_start_iso}
- **Query End Time (use this)**: {query_end_iso}

IMPORTANT: When calling query_loki or query_cortex, use these EXACT values:
- start_time: "{query_start_iso}"
- end_time: "{query_end_iso}"

## Query Hints

{logql_hints}

{promql_hints}{dependency_hints}

## Instructions

1. Query relevant logs and metrics using the timestamps above
2. Identify the root cause of this alert
3. Generate a comprehensive RCA report with remediation steps

Begin your analysis by querying for relevant data."""

    def _detect_dependencies(self, labels: dict, alertname: str) -> list[str]:
        """
        Detect potential service dependencies from alert context.

        Args:
            labels: Alert labels
            alertname: Alert name

        Returns:
            List of potential dependency service names
        """
        dependencies = []

        # Common dependency patterns based on service names
        service = labels.get("service", "")
        alertname_lower = alertname.lower()

        # API services often depend on databases
        if any(x in service.lower() for x in ["api", "backend", "service"]):
            dependencies.extend(["postgres", "mysql", "redis", "mongodb"])

        # If it's a database alert, check for client services
        if any(x in alertname_lower for x in ["database", "db", "postgres", "mysql", "redis"]):
            dependencies.append("all-api-services")

        # Network issues might affect downstream
        if (
            any(x in alertname_lower for x in ["network", "connection", "timeout"])
            and "namespace" in labels
        ):
            dependencies.append(f"all-services-in-{labels['namespace']}")

        # If there's a job label, look for related services
        if "job" in labels:
            job = labels["job"]
            if "-" in job:
                base = job.rsplit("-", 1)[0]
                dependencies.append(f"{base}-*")

        return dependencies[:5]  # Limit to 5 suggestions

    def _format_incident_for_analysis(self, incident: Incident, alerts: list[Alert]) -> str:
        """Format incident with multiple alerts for LLM's analysis."""
        from datetime import timedelta

        alerts_data = []
        primary_alert_id = incident.primary_alert_id
        earliest_alert_time = None

        for alert in alerts:
            alert_info = {
                "alertname": alert.alertname,
                "severity": alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity),
                "status": alert.status.value if hasattr(alert.status, "value") else str(alert.status),
                "labels": alert.labels,
                "annotations": alert.annotations or {},
                "starts_at": alert.starts_at.isoformat() if alert.starts_at else None,
                "is_primary": str(alert.id) == str(primary_alert_id) if primary_alert_id else False,
            }
            alerts_data.append(alert_info)

            # Track earliest alert time
            if alert.starts_at:
                if earliest_alert_time is None or alert.starts_at < earliest_alert_time:
                    earliest_alert_time = alert.starts_at

        # Sort by start time
        alerts_data.sort(key=lambda x: x.get("starts_at", ""))

        # Calculate query time window
        now = datetime.now(UTC)
        if earliest_alert_time:
            query_start = earliest_alert_time - timedelta(minutes=15)
        elif incident.started_at:
            query_start = incident.started_at - timedelta(minutes=15)
        else:
            query_start = now - timedelta(minutes=30)

        query_end = now

        # Format as ISO strings
        query_start_iso = query_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        query_end_iso = query_end.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Store for use in tool calls (to override hallucinated timestamps)
        self.query_start_time = query_start_iso
        self.query_end_time = query_end_iso

        # Build initial timeline from alerts
        initial_timeline = []
        for i, alert_info in enumerate(alerts_data):
            timeline_entry = {
                "timestamp": alert_info["starts_at"],
                "event": f"Alert fired: {alert_info['alertname']}",
                "severity": alert_info["severity"],
                "is_primary": alert_info.get("is_primary", False),
                "order": i + 1,
            }
            initial_timeline.append(timeline_entry)

        incident_data = {
            "title": incident.title,
            "severity": incident.severity.value if hasattr(incident.severity, "value") else str(incident.severity),
            "affected_services": incident.affected_services,
            "started_at": incident.started_at.isoformat() if incident.started_at else None,
            "alert_count": len(alerts),
            "correlation_reason": incident.correlation_reason,
        }

        return f"""Please analyze the following incident with multiple correlated alerts and determine the root cause:

## Incident Summary

```json
{json.dumps(incident_data, indent=2, default=str)}
```

## Correlated Alerts (in chronological order)

```json
{json.dumps(alerts_data, indent=2, default=str)}
```

## Initial Timeline (alerts only - enrich with logs/metrics)

```json
{json.dumps(initial_timeline, indent=2, default=str)}
```

## Correlation Context

- **Why correlated**: {incident.correlation_reason or 'Time proximity and label matching'}
- **Primary alert (suspected root cause)**: The alert marked with `is_primary: true` is the system's initial guess
- **Your task**: Verify or correct this assessment based on evidence

## Time Context - USE THESE EXACT TIMESTAMPS

- Incident Start: {incident_data.get('started_at', 'Unknown')}
- Current Time: {now.isoformat()}
- **Query Start Time (use this)**: {query_start_iso}
- **Query End Time (use this)**: {query_end_iso}

IMPORTANT: When calling query_loki or query_cortex, use these EXACT values:
- start_time: "{query_start_iso}"
- end_time: "{query_end_iso}"

## Instructions

1. Analyze the sequence of alerts to understand the cascade of events
2. Query relevant logs and metrics using the timestamps above
3. Identify the PRIMARY root cause (the first failure that triggered the chain)
4. Distinguish between the root cause and secondary symptoms
5. Generate a comprehensive RCA report with:
   - Clear identification of root cause vs symptoms
   - Timeline showing the progression of failures (include all alerts plus key log/metric events)
   - Evidence from logs and metrics
   - Remediation steps addressing both the root cause and preventive measures

## IMPORTANT: You MUST use tools

1. FIRST: Call the `query_loki` tool to search for error logs from the primary alert's service
2. THEN: Analyze the log results to understand what happened
3. FINALLY: Call the `generate_report` tool with your findings

Do NOT respond with text only. You MUST call query_loki first to investigate.

Begin by calling query_loki for: {alerts_data[0].get('labels', {}).get('service') or alerts_data[0].get('labels', {}).get('device', 'unknown')}"""

    async def _execute_tool(self, tool_name: str, tool_input: dict) -> dict[str, Any]:
        """Execute a tool and return the result."""
        self.tool_calls += 1

        # Normalize parameters to handle common LLM mistakes
        tool_input = self._normalize_tool_input(tool_name, tool_input)

        if tool_name == "query_loki":
            return await execute_query_loki(**tool_input)
        elif tool_name == "query_cortex":
            return await execute_query_cortex(**tool_input)
        elif tool_name == "generate_report":
            return execute_generate_report(**tool_input)
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    def _normalize_tool_input(self, tool_name: str, tool_input: dict) -> dict:
        """
        Normalize tool input parameters to handle common LLM mistakes.

        Maps common parameter name variations to expected names and provides defaults.
        """
        normalized = dict(tool_input)

        if tool_name == "query_loki":
            # Handle parameter name variations
            param_mappings = {
                "end": "end_time",
                "start": "start_time",
                "query": "logql_query",
                "logql": "logql_query",
            }
            for wrong, correct in param_mappings.items():
                if wrong in normalized and correct not in normalized:
                    normalized[correct] = normalized.pop(wrong)
                elif wrong in normalized and correct in normalized:
                    # Remove the duplicate wrong param
                    del normalized[wrong]

            # CRITICAL: Override timestamps with stored values to prevent hallucination
            # LLMs often hallucinate timestamps from training data (e.g., 2023 dates)
            if self.query_start_time and self.query_end_time:
                normalized["start_time"] = self.query_start_time
                normalized["end_time"] = self.query_end_time

        elif tool_name == "query_cortex":
            param_mappings = {
                "end": "end_time",
                "start": "start_time",
                "query": "promql_query",
                "promql": "promql_query",
            }
            for wrong, correct in param_mappings.items():
                if wrong in normalized and correct not in normalized:
                    normalized[correct] = normalized.pop(wrong)
                elif wrong in normalized and correct in normalized:
                    del normalized[wrong]

            # CRITICAL: Override timestamps with stored values to prevent hallucination
            if self.query_start_time and self.query_end_time:
                normalized["start_time"] = self.query_start_time
                normalized["end_time"] = self.query_end_time

        elif tool_name == "generate_report":
            # Handle parameter name variations
            param_mappings = {
                "root": "root_cause",
                "cause": "root_cause",
                "confidence": "confidence_score",
                "score": "confidence_score",
            }
            for wrong, correct in param_mappings.items():
                if wrong in normalized and correct not in normalized:
                    normalized[correct] = normalized.pop(wrong)

            # Provide defaults for missing required fields
            if "root_cause" not in normalized:
                normalized["root_cause"] = normalized.get("summary", "Root cause could not be determined from available evidence")

            if "confidence_score" not in normalized:
                # Try to infer from text or default to 50
                normalized["confidence_score"] = 50

            if "summary" not in normalized:
                # Use root_cause as summary if not provided
                normalized["summary"] = normalized.get("root_cause", "Analysis completed")

            # Ensure confidence_score is an integer
            try:
                normalized["confidence_score"] = int(normalized["confidence_score"])
            except (ValueError, TypeError):
                normalized["confidence_score"] = 50

        return normalized

    async def analyze_alert(self, alert: Alert | dict) -> dict[str, Any]:
        """
        Analyze a single alert and generate an RCA report.

        Args:
            alert: Alert object or dictionary with alert data

        Returns:
            dict: RCA report data or error information
        """
        self.start_time = time.time()
        self.total_tokens = 0
        self.tool_calls = 0

        prompt = self._format_alert_for_analysis(alert)
        return await self._run_agent_loop(prompt)

    async def analyze_incident(self, incident: Incident, alerts: list[Alert]) -> dict[str, Any]:
        """
        Analyze an incident with multiple correlated alerts.

        Args:
            incident: Incident object
            alerts: List of correlated alerts

        Returns:
            dict: RCA report data or error information
        """
        self.start_time = time.time()
        self.total_tokens = 0
        self.tool_calls = 0

        prompt = self._format_incident_for_analysis(incident, alerts)
        return await self._run_agent_loop(prompt)

    async def _run_agent_loop(self, initial_prompt: str) -> dict[str, Any]:
        """
        Run the agentic loop until the report is generated.

        Args:
            initial_prompt: The initial prompt for analysis

        Returns:
            dict: RCA report data or error information
        """
        messages: list[dict[str, Any]] = [{"role": "user", "content": initial_prompt}]
        iteration = 0
        report_data = None

        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"RCA Agent iteration {iteration}/{self.max_iterations} using {self.llm.name}")

            try:
                response = await self.llm.chat(
                    messages=messages,
                    tools=self.tools,
                    system_prompt=self.system_prompt,
                    max_tokens=4096,
                    temperature=0.0,
                )

                # Track token usage
                self.total_tokens += response.usage.get("input_tokens", 0)
                self.total_tokens += response.usage.get("output_tokens", 0)

                # Check if LLM is done (no tool calls)
                if response.is_complete:
                    if report_data:
                        return self._finalize_report(report_data)

                    # Model stopped without generating report - prompt it to continue
                    if self.tool_calls > 0 and iteration < self.max_iterations - 1:
                        logger.info(
                            f"Model stopped after {self.tool_calls} tool calls without report, prompting to continue"
                        )
                        if response.content:
                            messages.append({"role": "assistant", "content": response.content})

                        # More forceful prompt after several attempts
                        force_level = "CRITICAL" if iteration >= 5 else "IMPORTANT"
                        messages.append({
                            "role": "user",
                            "content": (
                                f"**{force_level}**: You MUST call the `generate_report` tool NOW to complete this analysis.\n\n"
                                "Based on the evidence gathered (or lack thereof), call generate_report with:\n"
                                "- root_cause: Your best assessment of what caused the issue (even if uncertain)\n"
                                "- confidence_score: 0-100 (use lower scores if evidence is limited)\n"
                                "- summary: Brief description of the incident and findings\n"
                                "- remediation_steps: Array with at least one step having 'priority' and 'action' fields\n\n"
                                "If you couldn't find logs or metrics, that's OK - report what you know from the alert itself.\n"
                                "DO NOT respond with text. ONLY call the generate_report tool."
                            ),
                        })
                        continue

                    logger.info("Agent completed analysis without generating report")
                    # Fallback: Try to create a basic report from text responses
                    text_responses = [
                        m.get("content", "") for m in messages
                        if m.get("role") == "assistant" and isinstance(m.get("content"), str)
                    ]
                    combined_text = "\n".join(text_responses)
                    if combined_text and len(combined_text) > 50:
                        # Create a fallback report from the model's text analysis
                        logger.info("Creating fallback report from text analysis")
                        return self._create_fallback_report(combined_text)

                    return {
                        "success": False,
                        "error": "Agent completed without generating a report",
                        "text_response": response.content,
                        "metadata": self._get_metadata(),
                    }

                # Process tool calls
                if response.has_tool_calls:
                    # Add assistant message to conversation
                    messages.append(self.llm.format_assistant_message(response))

                    for tool_call in response.tool_calls:
                        self.tool_calls += 1
                        logger.info(f"Executing tool: {tool_call.name}")
                        result = await self._execute_tool(tool_call.name, tool_call.arguments)

                        # Check if this is the final report
                        if tool_call.name == "generate_report" and result.get("success"):
                            report_data = result.get("report")

                        # Add tool result to conversation
                        tool_result_msg = self.llm.format_tool_result(
                            tool_call_id=tool_call.id,
                            tool_name=tool_call.name,
                            result=result,
                        )
                        messages.append(tool_result_msg)

                    # If we got a report, we can return
                    if report_data:
                        return self._finalize_report(report_data)

                else:
                    # No tool calls and not complete - unusual state
                    logger.warning(f"Unexpected state: stop_reason={response.stop_reason}")
                    if response.content:
                        messages.append({"role": "assistant", "content": response.content})
                        messages.append({
                            "role": "user",
                            "content": "Please continue your analysis and generate the report using the generate_report tool."
                        })

            except Exception as e:
                logger.error(f"LLM error: {e}")
                # Check for rate limiting
                if "rate" in str(e).lower() or "429" in str(e):
                    await self._handle_rate_limit()
                    continue
                return {
                    "success": False,
                    "error": f"LLM error ({self.llm.name}): {str(e)}",
                    "metadata": self._get_metadata(),
                }

        # Max iterations reached
        logger.warning(f"Max iterations ({self.max_iterations}) reached")
        if report_data:
            return self._finalize_report(report_data)

        # Try to create a fallback report from any text analysis in the conversation
        text_responses = [
            m.get("content", "") for m in messages
            if m.get("role") == "assistant" and isinstance(m.get("content"), str)
        ]
        combined_text = "\n".join(text_responses)
        if combined_text and len(combined_text) > 50:
            logger.info("Max iterations reached - creating fallback report from conversation")
            return self._create_fallback_report(combined_text)

        # Last resort: Create a minimal report based on the initial prompt
        logger.info("Max iterations reached - creating minimal report from alerts")
        return self._create_minimal_report(initial_prompt, messages)

    def _finalize_report(self, report_data: dict) -> dict[str, Any]:
        """Finalize the report with metadata."""
        return {
            "success": True,
            "report": report_data,
            "metadata": self._get_metadata(),
        }

    def _create_fallback_report(self, text_analysis: str) -> dict[str, Any]:
        """
        Create a basic report from text analysis when the model doesn't call generate_report.

        This is a fallback for models that provide good analysis in text form
        but don't reliably use tool calling (e.g., smaller local models).
        """
        # Extract a summary from the first substantial response
        lines = text_analysis.strip().split("\n")
        summary_lines = [line for line in lines[:5] if line.strip() and len(line) > 20]
        summary = " ".join(summary_lines)[:500] if summary_lines else "Analysis completed via text response"

        # Try to identify potential root cause from the text
        root_cause = "Unable to definitively determine root cause"
        root_cause_indicators = ["root cause", "caused by", "issue is", "problem is", "due to"]
        for line in lines:
            line_lower = line.lower()
            for indicator in root_cause_indicators:
                if indicator in line_lower:
                    root_cause = line.strip()
                    break
            if root_cause != "Unable to definitively determine root cause":
                break

        # Extract any action items or remediation suggestions
        remediation_steps = []
        action_indicators = ["recommend", "suggest", "should", "need to", "must", "fix", "resolve", "restart", "scale"]
        for line in lines:
            line_lower = line.lower()
            for indicator in action_indicators:
                if indicator in line_lower and len(line) > 20:
                    remediation_steps.append({
                        "priority": "immediate",
                        "action": line.strip()[:200],
                        "risk": "low",
                    })
                    break
            if len(remediation_steps) >= 3:
                break

        # If no remediation found, add a generic one
        if not remediation_steps:
            remediation_steps.append({
                "priority": "immediate",
                "action": "Review the text analysis above for specific remediation steps",
                "risk": "low",
            })

        report = {
            "root_cause": root_cause[:500],
            "confidence_score": 30,  # Low confidence since this is a fallback
            "summary": f"[Fallback Report] {summary}",
            "timeline": [],
            "evidence": {"logs": [], "metrics": []},
            "remediation_steps": remediation_steps,
            "_fallback": True,
            "_text_analysis": text_analysis[:2000],  # Keep first 2000 chars for reference
        }

        logger.info(f"Created fallback report with {len(remediation_steps)} remediation steps")

        return {
            "success": True,
            "report": report,
            "metadata": self._get_metadata(),
            "warning": "This report was generated from text analysis as the model did not use the generate_report tool",
        }

    def _create_minimal_report(self, initial_prompt: str, messages: list[dict]) -> dict[str, Any]:
        """
        Create a minimal report when the model fails to generate one.

        This extracts information directly from the alert data in the initial prompt
        and any tool results in the conversation.
        """
        # Extract alert info from the initial prompt
        alert_name = "Unknown"
        service = "Unknown"
        description = "Analysis incomplete"

        # Try to parse alert details from the prompt
        if "alertname" in initial_prompt:
            import re
            alertname_match = re.search(r'"alertname":\s*"([^"]+)"', initial_prompt)
            if alertname_match:
                alert_name = alertname_match.group(1)

            service_match = re.search(r'"service":\s*"([^"]+)"', initial_prompt)
            if service_match:
                service = service_match.group(1)
            else:
                # Also check for 'device' label (used by network equipment)
                device_match = re.search(r'"device":\s*"([^"]+)"', initial_prompt)
                if device_match:
                    service = device_match.group(1)

            desc_match = re.search(r'"description":\s*"([^"]+)"', initial_prompt)
            if desc_match:
                description = desc_match.group(1)

            summary_match = re.search(r'"summary":\s*"([^"]+)"', initial_prompt)
            if summary_match:
                description = summary_match.group(1)

        # Build a basic report with proper schema-compliant format
        report = {
            "root_cause": f"Alert '{alert_name}' on service '{service}' - {description}",
            "confidence_score": 40,  # Low confidence since analysis was incomplete
            "summary": f"[Minimal Report] The RCA agent was unable to complete full analysis within iteration limits. "
                       f"Alert '{alert_name}' fired for service '{service}'. {description}. "
                       f"Manual investigation recommended.",
            "timeline": [{
                "timestamp": datetime.now(UTC).isoformat(),
                "event": f"Alert {alert_name} triggered investigation",
                "source": "alert",
                "details": None,
            }],
            "evidence": {
                "logs": [],
                "metrics": [],
            },
            "remediation_steps": [
                {
                    "priority": "immediate",
                    "action": f"Investigate {alert_name} on {service}",
                    "description": description,
                    "risk": "low",
                },
                {
                    "priority": "immediate",
                    "action": "Check service logs and metrics manually",
                    "description": "The automated analysis could not gather sufficient evidence. Manual log review recommended.",
                    "risk": "low",
                },
            ],
        }

        logger.info(f"Created minimal report for {alert_name} on {service}")

        return {
            "success": True,
            "report": report,
            "metadata": self._get_metadata(),
            "warning": "This is a minimal report created because the agent exceeded max iterations",
        }

    def _get_metadata(self) -> dict[str, Any]:
        """Get analysis metadata."""
        duration = time.time() - self.start_time if self.start_time else 0
        return {
            "provider": self.llm.name,
            "model": self.llm.model,
            "tokens_used": self.total_tokens,
            "duration_seconds": round(duration, 2),
            "tool_calls": self.tool_calls,
        }

    async def _handle_rate_limit(self) -> None:
        """Handle rate limit errors with backoff."""
        import asyncio

        wait_time = 5.0
        logger.info(f"Rate limited, waiting {wait_time}s before retry")
        await asyncio.sleep(wait_time)
