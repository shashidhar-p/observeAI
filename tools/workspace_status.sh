#!/bin/bash
# =============================================================================
# Workspace status script for Bazel stamping
# Provides git commit info for container image tagging
# =============================================================================

# Get git commit SHA
if git rev-parse HEAD >/dev/null 2>&1; then
    echo "STABLE_GIT_COMMIT $(git rev-parse HEAD)"
    echo "STABLE_GIT_SHORT_COMMIT $(git rev-parse --short HEAD)"
else
    echo "STABLE_GIT_COMMIT unknown"
    echo "STABLE_GIT_SHORT_COMMIT unknown"
fi

# Get git branch
if git rev-parse --abbrev-ref HEAD >/dev/null 2>&1; then
    echo "STABLE_GIT_BRANCH $(git rev-parse --abbrev-ref HEAD)"
else
    echo "STABLE_GIT_BRANCH unknown"
fi

# Check if working directory is clean
if git diff-index --quiet HEAD -- 2>/dev/null; then
    echo "STABLE_GIT_DIRTY false"
else
    echo "STABLE_GIT_DIRTY true"
fi

# Get build timestamp
echo "STABLE_BUILD_TIMESTAMP $(date -u +%Y-%m-%dT%H:%M:%SZ)"
