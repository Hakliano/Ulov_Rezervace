#!/usr/bin/env bash
# Návrat LIVE na známý bod (git tag/commit + volitelně DB/www ze zálohy).
#
#   bash deploy/rollback-live.sh live-20260720-0000
#   bash deploy/rollback-live.sh live-20260720-0000 20260720_000015
#                              ^git ref                 ^STAMP ze souborů backups/*_STAMP.*
set -euo pipefail

cd "$(dirname "$0")/.."
REF="${1:-}"
STAMP="${2:-}"

if [ -z "$REF" ]; then
  echo "Použití: bash deploy/rollback-live.sh <git-tag-nebo-sha> [backup-stamp]"
  echo "Příklad: bash deploy/rollback-live.sh live-20260720-0000 20260720_000015"
  echo "Dostupné tagy:"; git tag -l 'live-*' | tail -n 20
  echo "Dostupné zálohy:"; ls -1 backups/db_*.sql.gz 2>/dev/null | tail -n 10 || true
  exit 2
fi

echo "=== ROLLBACK na $REF (stamp=${STAMP:-jen git+rsync}) ==="
read -r -p "Opravdu rollback LIVE? napiš YES: " ok
[ "$ok" = "YES" ] || { echo "Zrušeno."; exit 1; }

echo "### Pojistná záloha aktuálního stavu"
bash deploy/backup.sh || true

echo "### Git"
git fetch origin --tags
git checkout --force -B deploy-rollback "$REF"
git reset --hard "$REF"

echo "### www z gitu"
mapfile -t DIRS < <(find . -maxdepth 1 -type d \( -name 'salon*' -o -name 'zdravi-*' -o -name 'remesla-*' -o -name 'provoz-*' \) -printf '%f\n' | sort)
for d in "${DIRS[@]:-}"; do
  mkdir -p "www/$d"
  rsync -a "$d/" "www/$d/"
done
[ -d presentace ] && rsync -a presentace/ www/presentace/

if [ -n "$STAMP" ]; then
  if [ -f "backups/www_${STAMP}.tar.gz" ]; then
    echo "### Obnova www z backups/www_${STAMP}.tar.gz"
    tar -xzf "backups/www_${STAMP}.tar.gz"
  fi
  if [ -f "backups/db_${STAMP}.sql.gz" ]; then
    echo "### Obnova DB z backups/db_${STAMP}.sql.gz"
    # Načti DB_* z .env
    set -a; [ -f .env ] && . ./.env; set +a
    gunzip -c "backups/db_${STAMP}.sql.gz" | docker compose exec -T db psql -U "${DB_USER:-ulov}" -d "${DB_NAME:-ulov}"
  fi
fi

docker compose up -d
docker compose exec -T api python manage.py migrate --noinput || true

echo "=== Rollback hotov. Ověř health a dema v prohlížeči. ==="
