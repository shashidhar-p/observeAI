# Multi-Agent AI Observability & RCA System

An AI-powered observability platform for automated Root Cause Analysis with pluggable LLM providers.

## Features

- **Automated Alert Triage**: Receive alerts from Prometheus Alert Manager and automatically analyze them
- **Multi-Alert Correlation**: Group related alerts into incidents based on time proximity and label matching
- **AI-Powered RCA**: Use LLM agents with tool calling to query logs (Loki) and metrics (Cortex)
- **Pluggable LLM Providers**: Support for multiple AI providers (OpenAI, Gemini, Ollama)
- **Remediation Suggestions**: Generate actionable remediation steps categorized by priority and risk
- **Real-time Dashboard**: Modern React dashboard with live incident monitoring
- **REST API**: Full API access to alerts, incidents, and RCA reports

## Screenshots

### Incidents Dashboard
Monitor all incidents with status filtering, severity indicators, and real-time auto-refresh.

![Incidents List](docs/screenshots/incidents-list.png)

### Correlated Alerts View
See all alerts grouped into an incident with timeline offsets and ROOT cause identification.

![Correlated Alerts](docs/screenshots/correlated-alerts.png)

### AI-Powered RCA Analysis
View detailed root cause analysis with confidence scores, evidence, and remediation steps.

![RCA Analysis](docs/screenshots/rca-analysis.png)

## Requirements

- Python 3.11+
- PostgreSQL 14+
- Loki (for logs)
- Cortex (for metrics)
- LLM API key (OpenAI, Gemini, or local Ollama)

## Quick Start

### Option A: Bazel Build (Recommended)

```bash
# Clone the repository
git clone https://github.com/shashidhar-p/observeAI.git
cd observeAI

# Install bazelisk (Bazel version manager)
# macOS: brew install bazelisk
# Linux: curl -L https://github.com/bazelbuild/bazelisk/releases/latest/download/bazelisk-linux-amd64 -o /usr/local/bin/bazel && chmod +x /usr/local/bin/bazel

# Build everything
bazel build //...

# Run tests
bazel test //...

# Start development servers
bazel run //:dev
```

See [specs/002-bazel-build-infra/quickstart.md](specs/002-bazel-build-infra/quickstart.md) for detailed Bazel usage.

### Option B: Traditional Setup

```bash
# Clone the repository
git clone https://github.com/shashidhar-p/observeAI.git
cd observeAI

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -e ".[dev]"
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
# Required: LLM_API_KEY, DATABASE_URL
```

### 3. Start Services with Docker

```bash
# Start PostgreSQL, Loki, and Cortex
docker-compose -f docker/docker-compose.yaml up -d
```

### 4. Run Database Migrations

```bash
# Apply database migrations
alembic upgrade head
```

### 5. Start the Application

```bash
# Run the server
python -m src.main
# or
uvicorn src.main:app --reload
```

The API will be available at http://localhost:8000
The Dashboard will be available at http://localhost:3001

## Dashboard

The React dashboard provides a modern, real-time interface for monitoring incidents and RCA reports.

### Features

| Feature | Description |
|---------|-------------|
| **Incident List** | View all incidents with status cards (Open, Analyzing, RCA Complete, Resolved) |
| **Search & Filter** | Filter by status, severity, or search by incident title/service |
| **Auto-Refresh** | Configurable auto-refresh (5s, 10s, 30s, 1m) for real-time monitoring |
| **Correlated Alerts** | View all alerts grouped into an incident with timeline offsets |
| **RCA Analysis** | Confidence gauge, root cause, summary, and evidence from logs/metrics |
| **Remediation Steps** | Prioritized remediation actions with risk levels and commands |
| **Event Timeline** | Chronological view of events from alerts, logs, and metrics |
| **Grafana Integration** | Direct links to explore logs in Grafana/Loki |

### Running the Dashboard

```bash
# With Bazel (recommended)
bazel run //:dev  # Starts both backend (8000) and dashboard (3001)

# Or standalone
cd dashboard && npm install && npm run dev
```

## API Endpoints

### Health
- `GET /health` - Basic health check
- `GET /health/ready` - Readiness check with dependency status

### Webhooks
- `POST /webhooks/alertmanager` - Receive alerts from Alert Manager

### Alerts
- `GET /api/v1/alerts` - List alerts with filtering
- `GET /api/v1/alerts/{id}` - Get alert by ID

### Incidents
- `GET /api/v1/incidents` - List incidents with filtering
- `GET /api/v1/incidents/{id}` - Get incident by ID
- `POST /api/v1/incidents/{id}/correlate` - Manually correlate alerts

### Reports
- `GET /api/v1/reports` - List RCA reports
- `GET /api/v1/reports/{id}` - Get report by ID
- `GET /api/v1/reports/{id}/export` - Export report (JSON/Markdown)

## Architecture

```
├── src/                    # Python backend
│   ├── api/                # FastAPI routes and schemas
│   ├── models/             # SQLAlchemy models (Alert, Incident, RCAReport)
│   ├── services/           # Business logic
│   │   ├── rca_agent.py    # LLM agent for RCA with tool calling
│   │   ├── llm.py          # Multi-provider LLM abstraction
│   │   ├── correlation_service.py  # Alert correlation
│   │   └── webhook.py      # Alert Manager webhook handler
│   ├── tools/              # LLM tool definitions
│   │   ├── query_loki.py   # LogQL queries for logs
│   │   ├── query_cortex.py # PromQL queries for metrics
│   │   └── generate_report.py  # Report generation
│   └── main.py             # FastAPI application entrypoint
│
├── dashboard/              # React frontend
│   ├── src/
│   │   ├── pages/
│   │   │   ├── IncidentsPage.tsx    # Incident list with filters
│   │   │   └── IncidentDetailPage.tsx  # RCA report viewer
│   │   ├── api/client.ts   # API client with SWR
│   │   └── types/          # TypeScript types
│   └── vite.config.ts      # Vite with API proxy
│
├── prometheus/             # Alerting rules
│   └── alerts/             # Network, host, service alerts
│
└── docker-compose.observability.yml  # Full stack deployment
```

## Configuration

See `.env.example` for all configuration options:

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider (openai, gemini, ollama) | `openai` |
| `LLM_API_KEY` | LLM API key | Required |
| `LLM_MODEL` | Model name | Provider default |
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql+asyncpg://rca:rca@localhost:5432/rca_db` |
| `LOKI_URL` | Loki server URL | `http://localhost:3100` |
| `CORTEX_URL` | Cortex server URL | `http://localhost:9009` |
| `CORRELATION_WINDOW_SECONDS` | Time window for alert correlation | `300` |

## Development

See **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** for the complete developer's guide, including:
- Infrastructure setup (Prometheus, Alertmanager, Loki, Cortex, Grafana)
- Bazel build commands
- Container image building
- Troubleshooting

### Running Tests

```bash
# Via Bazel (recommended)
bazel test //...

# Via pytest
pytest
```

### Linting

```bash
ruff check src/
ruff format src/
```

### Type Checking

```bash
mypy src/
```

## License

MIT License
