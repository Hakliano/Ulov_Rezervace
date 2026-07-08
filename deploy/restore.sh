#!/usr/bin/env bash
# Obnova zálohy PostgreSQL — ověření, že zálohu opravdu umíme obnovit.
#
# Drill (doporučeno vyzkoušet po prvním nasazení a poté občas):
#   backup.sh  →  nová (čistá) DB  →  restore  →  ověření dat
#
# Použití:
#   bash deploy/restore.sh backups/db_YYYYMMDD_HHMMSS.sql.gz            # do ověřovací DB
#   bash deploy/restore.sh backups/db_YYYYMMDD_HHMMSS.sql.gz ulov       # ostrá obnova (POZOR!)
set -euo pipefail

cd "$(dirname "$0")/.."   # kořen projektu
if [ -f .env ]; then set -a; . ./.env; set +a; fi

DB_USER="${DB_USER:-ulov}"
SRC="${1:-}"
TARGET="${2:-${DB_NAME:-ulov}_restore_test}"

if [ -z "$SRC" ] || [ ! -f "$SRC" ]; then
  echo "Použití: bash deploy/restore.sh <zaloha.sql.gz> [cilova_db]" >&2
  exit 1
fi

echo "### Vytvářím čistou databázi '$TARGET' ..."
docker compose exec -T db psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$TARGET\";"
docker compose exec -T db psql -U "$DB_USER" -d postgres -c "CREATE DATABASE \"$TARGET\";"

echo "### Obnovuji '$SRC' → '$TARGET' ..."
gunzip -c "$SRC" | docker compose exec -T db psql -U "$DB_USER" -d "$TARGET" >/dev/null

echo "### Kontrola obnovených dat:"
docker compose exec -T db psql -U "$DB_USER" -d "$TARGET" -c \
  "SELECT (SELECT count(*) FROM salons_salon) AS salonu,
          (SELECT count(*) FROM rezervace_rezervace) AS rezervaci;" || \
  echo "  (tabulky zatím prázdné nebo jiné schéma – ověřte ručně)"

echo "### Hotovo. Ověřovací DB: '$TARGET'."
echo "### Úklid ověřovací DB: docker compose exec -T db psql -U $DB_USER -d postgres -c 'DROP DATABASE \"$TARGET\";'"
