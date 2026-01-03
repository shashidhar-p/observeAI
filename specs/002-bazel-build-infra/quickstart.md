# Quickstart: Bazel Build Infrastructure

**Feature**: 002-bazel-build-infra | **Date**: 2026-01-03

## Prerequisites

- **bazelisk**: Bazel version manager (recommended over direct Bazel install)
- **Python 3.11+**: For backend builds
- **Node.js 18+**: For dashboard builds
- **pnpm**: Package manager for dashboard (installed via Bazel if missing)
- **Docker**: Optional, only for running container images locally

## Installation

### 1. Install Bazelisk

```bash
# macOS
brew install bazelisk

# Linux (download binary)
curl -L https://github.com/bazelbuild/bazelisk/releases/latest/download/bazelisk-linux-amd64 -o /usr/local/bin/bazel
chmod +x /usr/local/bin/bazel

# Verify
bazel --version
```

Bazelisk automatically downloads the correct Bazel version from `.bazelversion`.

### 2. Clone and Build

```bash
# Clone repository
git clone https://github.com/shashidhar-p/observeAI.git
cd observeAI

# Build everything (first build downloads dependencies)
bazel build //...

# Run tests
bazel test //...
```

## Common Commands

### Build

```bash
# Build all targets
bazel build //...

# Build specific target
bazel build //src:backend
bazel build //dashboard:dashboard_bundle

# Build container images
bazel build //containers:backend_image
bazel build //containers:dashboard_image
```

### Test

```bash
# Run all tests
bazel test //...

# Run specific tests
bazel test //tests/unit:backend_tests

# Run with verbose output
bazel test //... --test_output=all

# Run tests matching pattern
bazel test //tests/... --test_filter="test_*"
```

### Run

```bash
# Start backend server
bazel run //src:backend

# Start development mode (backend + dashboard with hot-reload)
bazel run //:dev

# Run container image locally
bazel run //containers:backend_image
docker run -p 8000:8000 bazel/containers:backend_image
```

### Container Images

```bash
# Build and push backend image
bazel run //containers:backend_push

# Build and push dashboard image
bazel run //containers:dashboard_push

# Load image into local Docker
bazel run //containers:backend_image -- --norun
docker load < bazel-bin/containers/backend_image/tarball.tar
```

## Development Workflow

### 1. Make Changes

Edit source files in `src/` or `dashboard/src/`.

### 2. Incremental Build

```bash
# Rebuild only affected targets
bazel build //...
```

Bazel automatically detects changes and rebuilds only what's necessary.

### 3. Run Tests

```bash
# Run affected tests
bazel test //...
```

Cached test results are reused for unchanged code.

### 4. Development Server

```bash
# Start with file watching (requires ibazel)
ibazel run //:dev
```

Changes trigger automatic rebuilds.

## Project Structure

```
observeAI/
├── MODULE.bazel         # Dependencies (bzlmod)
├── .bazelrc             # Build configuration
├── .bazelversion        # Bazel version (for bazelisk)
├── BUILD.bazel          # Root build file
│
├── src/
│   ├── BUILD.bazel      # Python targets
│   └── ...
│
├── dashboard/
│   ├── BUILD.bazel      # JS/TS targets
│   └── ...
│
├── containers/
│   ├── BUILD.bazel      # OCI image targets
│   └── ...
│
└── tests/
    ├── BUILD.bazel      # Test targets
    └── ...
```

## Configuration Files

### .bazelrc

```bash
# Enable bzlmod
common --enable_bzlmod

# Build optimizations
build --jobs=auto
build --experimental_remote_cache_compression

# Test settings
test --test_output=errors
test --test_summary=short

# CI settings
build:ci --remote_cache=...
```

### .bazelversion

```
7.0.0
```

## Troubleshooting

### Clean Build

```bash
# Remove all build outputs
bazel clean

# Remove all outputs including cache
bazel clean --expunge
```

### Dependency Issues

```bash
# Regenerate Python lockfile
bazel run //:pip_compile

# Update pnpm lockfile
cd dashboard && pnpm install
```

### Cache Issues

```bash
# Force rebuild without cache
bazel build //... --noremote_cache

# Check cache status
bazel info repository_cache
```

### Debug Build

```bash
# Verbose build output
bazel build //... --subcommands

# Show dependency graph
bazel query 'deps(//src:backend)' --output=graph | dot -Tpng > deps.png
```

## CI/CD Integration

The GitHub Actions workflow (`.github/workflows/bazel.yml`) automatically:

1. Builds all targets on PR
2. Runs all tests on PR
3. Pushes container images on merge to main

### Required Secrets

| Secret | Description |
|--------|-------------|
| `GITHUB_TOKEN` | Automatic, for cache and ghcr.io |

No additional secrets needed - uses GitHub's built-in token.

## Next Steps

1. Run `bazel build //...` to verify setup
2. Run `bazel test //...` to run tests
3. Start developing with `bazel run //:dev`
4. Push changes and let CI handle the rest
