#!/bin/bash
# Build dashboard using local node_modules
set -e
cd "$(dirname "$0")"
npm run build
