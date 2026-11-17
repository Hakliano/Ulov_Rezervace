#!/usr/bin/env bash
# Nainstaluje /etc/cron.d/postak-live-sync (nevolá sync — jen cron + log soubory).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CRON_SRC="$ROOT/deploy/postak/cron/postak-live-sync.cron"
for f in "$ROOT/deploy/postak/run-nightly-sync-modernik.sh" "$ROOT/deploy/postak/run-nightly-sync-hya.sh"; do
  chmod +x "$f"
done
install -m 0644 "$CRON_SRC" /etc/cron.d/postak-live-sync
touch /var/log/postak-sync-modernik.log /var/log/postak-sync-hya.log
chmod 0644 /var/log/postak-sync-*.log
echo "OK cron: /etc/cron.d/postak-live-sync"
grep -v '^#' /etc/cron.d/postak-live-sync | grep -v '^$' || true