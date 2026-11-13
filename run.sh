#!/usr/bin/env bash
# Keep the review site up on the box (restarts on crash). Logs: data/server.log
cd "$(dirname "$0")"
while true; do python3 server.py --port "${PORT:-8787}" >> data/server.log 2>&1; sleep 2; done
