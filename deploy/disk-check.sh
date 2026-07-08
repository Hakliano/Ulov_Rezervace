#!/usr/bin/env bash
# Monitoring obsazenosti disku — logy, zálohy, Docker image, certifikáty.
# Doporučeno v cronu (např. každou hodinu):
#   0 * * * * cd /opt/ulov && bash deploy/disk-check.sh >> /var/log/ulov-disk.log 2>&1
#
# Návratový kód: 0 = OK, 1 = varování (>=WARN), 2 = kritické (>=CRIT).
set -euo pipefail

WARN="${DISK_WARN:-80}"
CRIT="${DISK_CRIT:-90}"
TARGET="${DISK_PATH:-/}"

USAGE="$(df --output=pcent "$TARGET" | tail -1 | tr -dc '0-9')"
echo "[$(date)] Obsazenost $TARGET: ${USAGE}% (WARN=${WARN}%, CRIT=${CRIT}%)"

# Přehled hlavních žroutů místa (informativně).
echo "  Docker: $(docker system df --format '{{.Type}} {{.Size}}' 2>/dev/null | tr '\n' ' ' || echo n/a)"
[ -d ./backups ] && echo "  Zálohy: $(du -sh ./backups 2>/dev/null | cut -f1)"

if [ "$USAGE" -ge "$CRIT" ]; then
  echo "KRITICKÉ: disk $TARGET >= ${CRIT}% !" >&2
  # TODO: sem doplnit notifikaci (e-mail / webhook / Sentry message)
  # Tip na úklid: docker system prune -af  |  smazat staré zálohy
  exit 2
elif [ "$USAGE" -ge "$WARN" ]; then
  echo "VAROVÁNÍ: disk $TARGET >= ${WARN}%." >&2
  exit 1
fi
exit 0
