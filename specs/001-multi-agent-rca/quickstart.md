# Quickstart: Multi-Agent AI Observability & RCA System

**Branch**: `001-multi-agent-rca` | **Updated**: 2026-01-02

## Prerequisites

- Python 3.11+
- Node.js 18+ (for dashboard)
- Docker & Docker Compose
- One of: Anthropic API key, Google Gemini API key, or Ollama installed locally

## Quick Setup (10 minutes)

### 1. Clone and Setup

```bash
# Clone repository
git clone <repository-url>
cd observeAI

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
```

**.env key settings:**
```bash
# Choose LLM provider: 'anthropic', 'gemini', or 'ollama'
LLM_PROVIDER=gemini

# Gemini (FREE tier available)
GEMINI_API_KEY=your-key-from-aistudio.google.com

# OR Anthropic Claude
# ANTHROPIC_API_KEY=sk-ant-api03-...

# OR Ollama (local, free)
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=llama3.1:8b

# Database
DATABASE_URL=postgresql+asyncpg://rca:rca@localhost:5432/rca_db

# Observability backends
LOKI_URL=http://localhost:3100
CORTEX_URL=http://localhost:9009

# RCA Expert Context (optional)
# Enable network engineer expertise for better network-related RCA
RCA_EXPERT_CONTEXT_FILE=prompts/network_engineer.md
```

### 3. Start Full Observability Stack

```bash
# Start everything: PostgreSQL, Loki, Cortex, Prometheus, Alertmanager, Node Exporter, Promtail, Grafana
docker-compose -f docker-compose.observability.yml up -d

# Verify services are running
docker-compose -f docker-compose.observability.yml ps
```

**Services started:**
| Service | Port | Purpose |
|---------|------|---------|
| PostgreSQL | 5432 | RCA database |
| Loki | 3100 | Log aggregation |
| Cortex | 9009 | Metrics storage |
| Prometheus | 9090 | Metrics & alerting |
| Alertmanager | 9093 | Alert routing |
| Node Exporter | 9100 | Host metrics |
| Promtail | 9080 | Log collection |
| Grafana | 3000 | Dashboards |

### 4. Initialize Database

```bash
# Run database migrations
PYTHONPATH=. alembic upgrade head
```

### 5. Start Backend & Dashboard

```bash
# Terminal 1: Start backend
PYTHONPATH=. uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start dashboard
cd dashboard && npm install && npm run dev
```

### 6. Verify Installation

```bash
# Backend health check
curl http://localhost:8000/health
# Expected: {"status": "healthy", "version": "0.1.0"}

# Dashboard
open http://localhost:3001

# Prometheus
open http://localhost:9090

# Grafana (admin/admin)
open http://localhost:3000
```

---

## Test with Real Network Interface Alert

### Create a Virtual Interface

```bash
# Create veth pair
sudo ip link add veth0 type veth peer name veth1
sudo ip link set veth0 up
sudo ip link set veth1 up

# Verify
ip link show veth0
```

### Trigger Alert (bring interface down)

```bash
sudo ip link set veth0 down
```

### Watch the Magic

1. **Prometheus** detects `node_network_up{device="veth0"} == 0`
2. After 30s → Alert fires
3. **Alertmanager** sends webhook to RCA backend
4. **Gemini/Claude** analyzes and generates RCA
5. **Dashboard** shows incident with remediation steps

### View in Dashboard

Open http://localhost:3001 - you'll see:
- New incident "NetworkInterfaceDown" with **Analyzing** status (animated)
- Once complete: **RCA Complete** status with confidence score
- Remediation commands like `sudo ip link set veth0 up`

**Dashboard Features:**
- **Search**: Filter incidents by title, services, or correlation reason
- **Status Cards**: Click Total/Open/Analyzing/RCA Complete/Resolved to filter
- **Severity Filter**: Dropdown for critical/warning/info
- **Auto-refresh**: Configurable (Off, 5s, 10s, 30s, 1m)
- **Manual Refresh**: Click refresh button anytime

### Resolve (bring interface up)

```bash
sudo ip link set veth0 up
```

The incident will auto-resolve when Alertmanager sends the resolved webhook (within 30s).

---

## API Endpoints

### List Incidents
```bash
curl http://localhost:8000/api/v1/incidents
```

### Get Incident Details
```bash
curl http://localhost:8000/api/v1/incidents/{incident-id}
```

### Get RCA Report
```bash
curl http://localhost:8000/api/v1/incidents/{incident-id}/report
```

---

## Project Structure

```
observeAI/
├── src/                    # Python backend
│   ├── main.py             # FastAPI application
│   ├── config.py           # Environment configuration
│   ├── services/           # Business logic
│   │   ├── rca_agent.py    # RCA agent with tools
│   │   ├── llm/            # Multi-provider LLM support
│   │   ├── webhook.py      # Alert webhook handler
│   │   └── semantic_correlator.py
│   ├── tools/              # Agent tools
│   └── api/                # REST API
├── dashboard/              # React frontend
│   └── src/pages/
│       ├── IncidentsPage.tsx   # List with search, filters
│       └── IncidentDetail.tsx  # RCA report viewer
├── prompts/                # RCA expert contexts
│   └── network_engineer.md # Network engineering expertise
├── prometheus/             # Alert rules & config
│   ├── prometheus.yml
│   ├── alertmanager.yml
│   └── alerts/
│       ├── network_alerts.yml
│       ├── host_alerts.yml
│       └── service_alerts.yml
├── promtail-config.yml     # Log collection
└── docker-compose.observability.yml
```

---

## Switching LLM Providers

### Use Gemini (Free)
```bash
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key  # Get from https://aistudio.google.com/app/apikey
```

### Use Claude (Best quality)
```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

### Use Ollama (Local, offline)
```bash
# Install Ollama first: https://ollama.ai
ollama pull llama3.1:8b

LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

---

## Troubleshooting

### No RCA Report Generated
- Check backend logs: `tail -f /tmp/backend.log`
- Verify LLM provider is configured correctly
- Check Alertmanager is routing to webhook

### Low Confidence Score
- Ensure Promtail is collecting system logs
- Check Loki has logs: `curl http://localhost:3100/loki/api/v1/labels`

### Alert Not Firing
- Check Prometheus: http://localhost:9090/alerts
- Verify alert rule expression matches your interface name

---

## Next Steps

1. **Monitor real alerts** - Configure your existing Alertmanager to route to http://rca-system:8000/webhooks/alertmanager
2. **Add custom alert rules** - Edit `prometheus/alerts/*.yml`
3. **Tune remediation prompts** - Edit `src/services/rca_agent.py`
4. **View in Grafana** - Import dashboards for Loki/Prometheus
