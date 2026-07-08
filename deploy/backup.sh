#!/usr/bin/env bash
# Záloha produkce: PostgreSQL dump + kritická konfigurace.
# Doporučeno spouštět denně přes cron:
#   0 3 * * * cd /opt/ulov && bash deploy/backup.sh >> /var/log/ulov-backup.log 2>&1
set -euo pipefail

cd "$(dirname "$0")/.."   # kořen projektu

# Načtení DB_* z kořenového .env
if [ -f .env ]; then
  set -a; . ./.env; set +a
fi

DB_NAME="${DB_NAME:-ulov}"
DB_USER="${DB_USER:-ulov}"

BACKUP_DIR="${BACKUP_DIR:-./backups}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
STAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "### [$(date)] Záloha databáze $DB_NAME ..."
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_DIR/db_${STAMP}.sql.gz"

echo "### Záloha konfigurace ..."
tar -czf "$BACKUP_DIR/config_${STAMP}.tar.gz" \
  .env \
  docker-compose.yml \
  deploy/nginx \
  deploy/certbot/conf 2>/dev/null || true

echo "### Úklid záloh starších než ${KEEP_DAYS} dní ..."
find "$BACKUP_DIR" -type f -name '*.gz' -mtime +"$KEEP_DAYS" -delete

echo "### Hotovo. Zálohy v $BACKUP_DIR:"
ls -lh "$BACKUP_DIR" | tail -n 5
