# Multi-Agent AI Observability & RCA System

An AI-powered observability platform for automated Root Cause Analysis.

## Features

- **Automated Alert Triage**: Receive alerts from Prometheus Alert Manager and automatically analyze them
- **Multi-Alert Correlation**: Group related alerts into incidents based on time proximity and label matching
- **AI-Powered RCA**: Use Claude AI with tool calling to query logs (Loki) and metrics (Cortex)
- **Remediation Suggestions**: Generate actionable remediation steps categorized by priority and risk
- **REST API**: Full API access to alerts, incidents, and RCA reports

## Requirements

- Python 3.11+
- PostgreSQL 14+
- Loki (for logs)
- Cortex (for metrics)
- Anthropic API key

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
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
# Required: ANTHROPIC_API_KEY, DATABASE_URL
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
src/
├── api/           # FastAPI routes and schemas
├── models/        # SQLAlchemy models
├── services/      # Business logic
│   ├── rca_agent.py       # Claude AI agent for RCA
│   ├── correlation_service.py  # Alert correlation
│   ├── webhook.py         # Alert Manager webhook handler
│   └── ...
├── tools/         # Claude tool definitions
│   ├── query_loki.py      # LogQL queries
│   ├── query_cortex.py    # PromQL queries
│   └── generate_report.py # Report generation
├── config.py      # Configuration management
├── database.py    # Database setup
└── main.py        # Application entrypoint
```

## Configuration

See `.env.example` for all configuration options:

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key | Required |
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql+asyncpg://rca:rca@localhost:5432/rca_db` |
| `LOKI_URL` | Loki server URL | `http://localhost:3100` |
| `CORTEX_URL` | Cortex server URL | `http://localhost:9009` |
| `CORRELATION_WINDOW_SECONDS` | Time window for alert correlation | `300` |

## Development

### Running Tests

```bash
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
