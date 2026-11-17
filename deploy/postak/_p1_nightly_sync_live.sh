#!/usr/bin/env bash
# P1: záloha + fingerprint před/po, deploy kódu, cron (bez ručního sync).
set -euo pipefail
REF="${1:-origin/dev}"
ROOT=/opt/ulov
cd "$ROOT"
STAMP=$(date -u +%Y%m%d-%H%M%S)
BACKUP="/root/backups/postak-live-pre-nightly-sync-${STAMP}.dump"
echo "=== PRE fingerprint ==="
bash deploy/postak/_live_fingerprints_postak.sh pre
echo "=== backup postak_live ==="
docker exec postak-live-db-1 pg_dump -U postak -Fc postak_live >"$BACKUP"
echo "backup=$BACKUP"
echo "=== deploy postak $REF ==="
bash deploy/postak/deploy-live-postak.sh "$REF"
PRE_GIT=$(docker exec -w /app ulov-live-postak git rev-parse HEAD 2>/dev/null || true)
echo "=== install cron ==="
bash deploy/postak/install-postak-live-sync-cron.sh
echo "=== POST fingerprint (data must match) ==="
bash deploy/postak/_live_fingerprints_postak.sh post
echo "=== cron check ==="
cat /etc/cron.d/postak-live-sync
echo "DONE pre_git=$PRE_GIT deployed=$REF"