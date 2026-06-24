#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-${KANOJO_PEER_BASE_URL:-http://kanojo-pc.local:8787}}"
TEXT="${TEXT:-prewarm pc inference node}"

curl -fsS \
    -X POST "${BASE_URL%/}/node/inference/prewarm" \
    -H "Content-Type: application/json" \
    -d "{\"text\":\"$TEXT\"}"
echo
