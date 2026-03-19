#!/bin/bash
set -euo pipefail

# Deploy helper to reduce "pulled but not restarted" mistakes.
# Run this on the Aliyun server inside the Inkstone repo directory.

echo "==============================================="
echo " Inkstone Aliyun deploy"
echo "==============================================="

cd "$(dirname "$0")"
echo "Working directory: $(pwd)"

echo ""
echo "Pulling latest code..."
git pull

export INKSTONE_RELEASE="${INKSTONE_RELEASE:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
echo "Release: ${INKSTONE_RELEASE}"

echo ""
echo "Running DB migrations..."
./run_migration_on_server.sh

echo ""
echo "Restarting service (inkstone)..."
sudo systemctl restart inkstone

echo ""
echo "Done. If admin ever looks stale, check the admin sidebar 'Release:' stamp."

