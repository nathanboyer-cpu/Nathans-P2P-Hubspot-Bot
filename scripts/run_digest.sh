#!/usr/bin/env bash
# Daily P2P HubSpot digest (Slack + optional Claude). Loads .env from repo root.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p "$ROOT/logs"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  exec "$ROOT/.venv/bin/python" -m p2p_digest.main "$@"
else
  exec python3 -m p2p_digest.main "$@"
fi
