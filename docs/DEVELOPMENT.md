# Developer's Guide

Complete guide for setting up and running the observeAI development environment.

## Prerequisites

- **Bazelisk**: Bazel version manager
- **Docker & Docker Compose**: For infrastructure services
- **Python 3.11+**: For local development without Bazel
- **Node.js 18+**: For dashboard development

### Install Bazelisk

```bash
# macOS
brew install bazelisk

# Linux
curl -L https://github.com/bazelbuild/bazelisk/releases/latest/download/bazelisk-linux-amd64 -o /usr/local/bin/bazel
chmod +x /usr/local/bin/bazel

# Verify
bazel --version
```

## Quick Start

```bash
# 1. Clone repository
git clone https://github.com/shashidhar-p/observeAI.git
cd observeAI

# 2. Copy environment file
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 3. Deploy everything (infrastructure + app containers)
bazel run //:deploy

# OR for development with hot-reload:
docker-compose -f docker-compose.observability.yml up -d
PYTHONPATH=. alembic upgrade head
bazel run //:dev
```

## Infrastructure Services

### Option A: Full Observability Stack (Recommended)

```bash
docker-compose -f docker-compose.observability.yml up -d
```

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| Prometheus | 9090 | http://localhost:9090 | Metrics scraping & alerting |
| Alertmanager | 9093 | http://localhost:9093 | Alert routing to app |
| Node Exporter | 9100 | http://localhost:9100 | Host metrics (CPU, memory, disk) |
| Loki | 3100 | http://localhost:3100 | Log aggregation |
| Cortex | 9009 | http://localhost:9009 | Long-term metrics storage |
| Promtail | - | - | Ships logs to Loki |
| Grafana | 3000 | http://localhost:3000 | Dashboards (admin/admin) |

### Option B: Minimal Development Stack

```bash
docker-compose -f docker/docker-compose.yaml up -d
```

| Service | Port | Purpose |
|---------|------|---------|
| PostgreSQL | 5432 | Database (rca:rca@rca_db) |
| Loki | 3100 | Log storage (stub) |
| Cortex | 9009 | Metrics storage (stub) |

### Managing Infrastructure

```bash
# Start services
docker-compose -f docker-compose.observability.yml up -d

# View logs
docker-compose -f docker-compose.observability.yml logs -f

# Stop services
docker-compose -f docker-compose.observability.yml down

# Stop and remove volumes (clean slate)
docker-compose -f docker-compose.observability.yml down -v
```

## Deployment Commands

### Deploy Full Stack

```bash
# Deploy everything: infrastructure + database + app containers
bazel run //:deploy
```

This command:
1. Builds backend and dashboard container images
2. Starts observability stack (Prometheus, Alertmanager, Loki, Cortex, Grafana)
3. Starts PostgreSQL database
4. Runs database migrations
5. Starts backend and dashboard containers

### Deploy Options

```bash
# Skip rebuilding container images
bazel run //:deploy -- --no-build

# Skip observability stack (only database + app)
bazel run //:deploy -- --no-observability

# Run in foreground (show logs)
bazel run //:deploy -- --no-detach
```

### Stop All Services

```bash
bazel run //:deploy-stop
```

## Bazel Build Commands

### Build

```bash
# Build all targets
bazel build //...

# Build specific targets
bazel build //src:backend              # Python backend
bazel build //dashboard:dashboard_bundle  # React dashboard
bazel build //containers:backend_image    # Backend container
bazel build //containers:dashboard_image  # Dashboard container
```

### Test

```bash
# Run all tests
bazel test //...

# Run specific tests
bazel test //tests/unit:test_schemas
bazel test //tests/unit:test_tools

# Run with verbose output
bazel test //... --test_output=all
```

### Run

```bash
# Start development servers (backend + dashboard with hot-reload)
bazel run //:dev

# Start backend only
bazel run //src:backend

# Start dashboard dev server only
bazel run //dashboard:dev_server
```

### Dependency Management

```bash
# Regenerate Python requirements lock file
bazel run //:pip_compile

# Update dashboard dependencies
cd dashboard && pnpm install
```

## Development Workflow

### Daily Development

```bash
# 1. Start infrastructure (if not running)
docker-compose -f docker-compose.observability.yml up -d

# 2. Start dev servers with hot-reload
bazel run //:dev

# Backend: http://localhost:8000
# Dashboard: http://localhost:3001
# API docs: http://localhost:8000/docs
```

### Making Changes

1. Edit source files in `src/` or `dashboard/src/`
2. Changes auto-reload (uvicorn for backend, Vite for dashboard)
3. Run tests: `bazel test //...`

### Adding Python Dependencies

1. Add dependency to `pyproject.toml`
2. Regenerate lock file: `bazel run //:pip_compile`
3. Rebuild: `bazel build //...`

### Adding Dashboard Dependencies

1. Add dependency: `cd dashboard && pnpm add <package>`
2. Rebuild: `bazel build //dashboard:dashboard_bundle`

## Container Images

### Build Container Images

```bash
# Build both images
bazel build //containers:backend_image
bazel build //containers:dashboard_image
```

### Run Containers Locally

```bash
# Load and run backend
bazel run //containers:backend_image
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql+asyncpg://rca:rca@host.docker.internal:5432/rca_db \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  bazel/containers:backend_image

# Load and run dashboard
bazel run //containers:dashboard_image
docker run -p 80:80 bazel/containers:dashboard_image
```

### Push to Registry

```bash
# Push to GitHub Container Registry (requires authentication)
bazel run //containers:backend_push
bazel run //containers:dashboard_push
```

## Project Structure

```
observeAI/
├── .bazelversion        # Bazel version (7.0.0)
├── MODULE.bazel         # Bazel dependencies (bzlmod)
├── .bazelrc             # Bazel configuration
├── BUILD.bazel          # Root build file
│
├── src/                 # Python backend
│   ├── BUILD.bazel
│   ├── main.py          # FastAPI entrypoint
│   ├── api/             # API routes
│   ├── models/          # SQLAlchemy models
│   ├── services/        # Business logic
│   └── tools/           # Claude AI tools
│
├── dashboard/           # React frontend
│   ├── BUILD.bazel
│   ├── package.json
│   └── src/
│
├── containers/          # OCI container definitions
│   └── BUILD.bazel
│
├── tests/               # Test suites
│   ├── BUILD.bazel
│   ├── unit/
│   └── integration/
│
├── docker-compose.observability.yml  # Full observability stack
└── docker/
    └── docker-compose.yaml           # Minimal dev stack
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | - | Claude API key |
| `DATABASE_URL` | No | `postgresql+asyncpg://rca:rca@localhost:5432/rca_db` | PostgreSQL connection |
| `LOKI_URL` | No | `http://localhost:3100` | Loki server URL |
| `CORTEX_URL` | No | `http://localhost:9009` | Cortex server URL |
| `CORRELATION_WINDOW_SECONDS` | No | `300` | Alert correlation window |
| `LOG_LEVEL` | No | `INFO` | Logging level |

## Troubleshooting

### Bazel Issues

```bash
# Clean build cache
bazel clean

# Full clean (including external dependencies)
bazel clean --expunge

# Rebuild everything
bazel build //...
```

### Database Issues

```bash
# Reset database
docker-compose -f docker-compose.observability.yml down -v
docker-compose -f docker-compose.observability.yml up -d
PYTHONPATH=. alembic upgrade head
```

### Port Conflicts

```bash
# Check what's using a port
lsof -i :8000
lsof -i :3001

# Kill process on port
kill -9 $(lsof -t -i :8000)
```

### View Service Logs

```bash
# All services
docker-compose -f docker-compose.observability.yml logs -f

# Specific service
docker-compose -f docker-compose.observability.yml logs -f prometheus
docker-compose -f docker-compose.observability.yml logs -f alertmanager
```

## CI/CD

GitHub Actions automatically:
1. Builds all targets on every PR
2. Runs all tests on every PR
3. Pushes container images on merge to `main`

See `.github/workflows/bazel.yml` for details.
