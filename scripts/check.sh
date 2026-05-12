#!/usr/bin/env bash
set -euo pipefail

bash -n data/probes/lib.sh data/probes/proxy_probe.sh scripts/check.sh
python3 -m py_compile data/config-ui/app.py
rm -rf data/config-ui/__pycache__

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose config >/dev/null
  docker compose -f docker-compose.dev.yml config >/dev/null
else
  printf 'docker compose not available; skipped compose config validation\n' >&2
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  running_services="$(docker compose ps --status running --services 2>/dev/null || true)"
  if grep -qx 'telegraf' <<< "$running_services"; then
    docker compose exec -T telegraf /probes/proxy_probe.sh >/dev/null
  else
    printf 'telegraf is not running; skipped runtime probe check\n' >&2
  fi
fi

printf 'check completed\n'
