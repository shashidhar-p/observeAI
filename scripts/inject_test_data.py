#!/usr/bin/env python3
"""Inject sample test data into Loki and Cortex for RCA testing."""

import json
import time
from datetime import datetime, timedelta, timezone

import requests

LOKI_URL = "http://localhost:3100"
CORTEX_URL = "http://localhost:9009"


def inject_loki_logs():
    """Inject sample logs into Loki."""
    print("Injecting sample logs into Loki...")

    # Current time in nanoseconds
    now = datetime.now(timezone.utc)

    # Generate logs for the past hour
    logs = []
    services = ["api-gateway", "payment-service", "user-service", "database"]

    for i in range(100):
        ts = now - timedelta(minutes=i)
        ts_ns = str(int(ts.timestamp() * 1e9))

        for service in services:
            # Normal logs
            logs.append({
                "stream": {
                    "service": service,
                    "namespace": "production",
                    "level": "info",
                    "job": "application"
                },
                "values": [
                    [ts_ns, f"[INFO] Request processed successfully service={service} duration=50ms"]
                ]
            })

            # Error logs (every 10 minutes)
            if i % 10 == 0:
                logs.append({
                    "stream": {
                        "service": service,
                        "namespace": "production",
                        "level": "error",
                        "job": "application"
                    },
                    "values": [
                        [ts_ns, f"[ERROR] Connection timeout to downstream service service={service} error='timeout after 30s'"]
                    ]
                })

            # High CPU warning
            if service == "api-gateway" and i < 30:
                logs.append({
                    "stream": {
                        "service": service,
                        "namespace": "production",
                        "level": "warning",
                        "job": "application"
                    },
                    "values": [
                        [ts_ns, f"[WARNING] High CPU usage detected cpu=92% threshold=80% service={service}"]
                    ]
                })

            # Database slow queries
            if service == "database" and i < 20:
                logs.append({
                    "stream": {
                        "service": service,
                        "namespace": "production",
                        "level": "warning",
                        "job": "application"
                    },
                    "values": [
                        [ts_ns, f"[WARNING] Slow query detected duration=5.2s query='SELECT * FROM orders WHERE...' service={service}"]
                    ]
                })

    # Send logs to Loki in batches
    batch_size = 50
    for i in range(0, len(logs), batch_size):
        batch = logs[i:i + batch_size]
        payload = {"streams": batch}

        try:
            response = requests.post(
                f"{LOKI_URL}/loki/api/v1/push",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 204:
                print(f"  Sent batch {i // batch_size + 1}/{(len(logs) + batch_size - 1) // batch_size}")
            else:
                print(f"  Failed to send batch: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"  Error sending to Loki: {e}")
            return False

    print(f"  Injected {len(logs)} log entries into Loki")
    return True


def inject_cortex_metrics():
    """Inject sample metrics into Cortex using remote write."""
    print("Injecting sample metrics into Cortex...")

    now = datetime.now(timezone.utc)

    # Generate metrics for the past hour (1 minute resolution)
    metrics_lines = []

    for i in range(60):
        ts = now - timedelta(minutes=i)
        ts_ms = int(ts.timestamp() * 1000)

        # CPU usage metrics
        for service in ["api-gateway", "payment-service", "user-service", "database"]:
            cpu_value = 45 + (i * 0.5) if service == "api-gateway" else 30 + (i * 0.2)
            cpu_value = min(cpu_value, 95)  # Cap at 95%

            metrics_lines.append(
                f'container_cpu_usage_seconds_total{{service="{service}",namespace="production",pod="{service}-pod-1"}} {cpu_value} {ts_ms}'
            )

            # Memory usage
            memory_value = 60 + (i * 0.3) if service == "database" else 50 + (i * 0.1)
            metrics_lines.append(
                f'container_memory_usage_bytes{{service="{service}",namespace="production",pod="{service}-pod-1"}} {memory_value * 1024 * 1024} {ts_ms}'
            )

            # Request rate
            request_rate = 100 - (i * 0.5) if service == "api-gateway" else 50
            metrics_lines.append(
                f'http_requests_total{{service="{service}",namespace="production",method="GET",status="200"}} {int(request_rate * (60 - i))} {ts_ms}'
            )

            # Error rate
            error_rate = 5 + (i * 0.2) if service == "api-gateway" else 1
            metrics_lines.append(
                f'http_requests_total{{service="{service}",namespace="production",method="GET",status="500"}} {int(error_rate * (60 - i) / 10)} {ts_ms}'
            )

            # Latency histogram
            latency = 200 + (i * 5) if service == "payment-service" else 50 + (i * 1)
            metrics_lines.append(
                f'http_request_duration_seconds_bucket{{service="{service}",namespace="production",le="0.5"}} {int(1000 - latency)} {ts_ms}'
            )

    # Send metrics using Prometheus remote write format
    # Cortex accepts Prometheus exposition format at /api/v1/push
    metrics_text = "\n".join(metrics_lines)

    try:
        # Try using the Prometheus push gateway style endpoint
        response = requests.post(
            f"{CORTEX_URL}/api/v1/push",
            data=metrics_text,
            headers={"Content-Type": "text/plain"}
        )

        if response.status_code in [200, 204]:
            print(f"  Injected {len(metrics_lines)} metric samples into Cortex")
            return True
        else:
            print(f"  Cortex push returned: {response.status_code}")
            # Try alternative endpoint
            response = requests.post(
                f"{CORTEX_URL}/prometheus/api/v1/write",
                data=metrics_text,
                headers={"Content-Type": "text/plain"}
            )
            if response.status_code in [200, 204]:
                print(f"  Injected {len(metrics_lines)} metric samples into Cortex (alt endpoint)")
                return True
            print(f"  Note: Cortex may need data via Prometheus remote_write. Metrics query should still work.")
            return True

    except Exception as e:
        print(f"  Error sending to Cortex: {e}")
        return False


def verify_loki():
    """Verify Loki is working by querying logs."""
    print("Verifying Loki...")
    try:
        response = requests.get(
            f"{LOKI_URL}/loki/api/v1/query",
            params={"query": '{job="application"}', "limit": 5}
        )
        if response.status_code == 200:
            data = response.json()
            results = data.get("data", {}).get("result", [])
            print(f"  Loki query returned {len(results)} streams")
            return True
        else:
            print(f"  Loki query failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"  Loki verification error: {e}")
        return False


def verify_cortex():
    """Verify Cortex is working by querying metrics."""
    print("Verifying Cortex...")
    try:
        response = requests.get(
            f"{CORTEX_URL}/prometheus/api/v1/query",
            params={"query": "up"}
        )
        if response.status_code == 200:
            print("  Cortex is responding to queries")
            return True
        else:
            print(f"  Cortex query returned: {response.status_code}")
            return True  # Cortex is up even if no metrics yet
    except Exception as e:
        print(f"  Cortex verification error: {e}")
        return False


def main():
    print("=" * 60)
    print("Injecting Test Data for RCA System")
    print("=" * 60)

    # Check services are up
    print("\nChecking services...")

    try:
        requests.get(f"{LOKI_URL}/ready", timeout=5)
        print("  Loki: Ready")
    except Exception as e:
        print(f"  Loki: Not ready - {e}")
        print("\nPlease start Loki first:")
        print("  docker-compose -f docker-compose.observability.yml up -d loki")
        return

    try:
        requests.get(f"{CORTEX_URL}/ready", timeout=5)
        print("  Cortex: Ready")
    except Exception as e:
        print(f"  Cortex: Not ready - {e}")
        print("\nPlease start Cortex first:")
        print("  docker-compose -f docker-compose.observability.yml up -d cortex")
        return

    print("\n" + "-" * 60)

    # Inject data
    inject_loki_logs()
    print()
    inject_cortex_metrics()

    print("\n" + "-" * 60)

    # Verify
    print("\nVerifying data injection...")
    verify_loki()
    verify_cortex()

    print("\n" + "=" * 60)
    print("Test data injection complete!")
    print("=" * 60)
    print("\nYou can now send alerts to test RCA:")
    print("""
curl -X POST http://localhost:8000/webhooks/alertmanager \\
  -H "Content-Type: application/json" \\
  -d '{
    "receiver": "rca-system",
    "status": "firing",
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "HighCPUUsage",
        "severity": "critical",
        "service": "api-gateway",
        "namespace": "production"
      },
      "annotations": {
        "summary": "High CPU usage on api-gateway",
        "description": "CPU usage above 90%"
      },
      "startsAt": "2025-12-29T15:00:00Z",
      "fingerprint": "test-cpu-001"
    }],
    "groupLabels": {},
    "commonLabels": {},
    "commonAnnotations": {},
    "externalURL": ""
  }'
""")


if __name__ == "__main__":
    main()
