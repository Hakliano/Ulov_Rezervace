#!/usr/bin/env bash
# Nasazení LIVE výhradně z GitHub MAIN (ne z DEV).
#   bash deploy/deploy-live.sh                 # origin/main
#   bash deploy/deploy-live.sh live-20260720-0145
#
# Vyžaduje: čistý / očekávaný stav v /opt/ulov, Docker, SSH na serveru.
set -euo pipefail

cd "$(dirname "$0")/.."
REF="${1:-origin/main}"
STAMP="$(date +%Y%m%d_%H%M%S)"
ROOT="$(pwd)"

echo "=== LIVE deploy z GitHub ref: $REF ==="

if [ ! -d .git ]; then
  echo "FAIL: $ROOT není git repo"
  exit 1
fi

echo "### 1) Záloha před deployem"
bash deploy/backup.sh
tar -czf "/root/www-predeploy-${STAMP}.tar.gz" -C "$ROOT" www 2>/dev/null || true

echo "### 2) Fetch + checkout"
git fetch origin --tags
git checkout --force -B deploy-live "$REF"
git reset --hard "$REF"
GIT_SHA="$(git rev-parse --short HEAD)"
echo "GIT_SHA=$GIT_SHA"

echo "### 3) Kompletnost statiky (příklad: běžné dema — uprav dle potřeby)"
# Kontrola všech salon*/vertikál přítomných ve stromu
mapfile -t DIRS < <(find . -maxdepth 1 -type d \( -name 'salon*' -o -name 'zdravi-*' -o -name 'remesla-*' -o -name 'provoz-*' \) -printf '%f\n' | sort)
if [ "${#DIRS[@]}" -gt 0 ]; then
  bash deploy/pre-deploy-check.sh "${DIRS[@]}"
fi
if [ -d presentace ]; then
  bash deploy/pre-deploy-check.sh presentace || true
fi

echo "### 4) Sync repo → www/ (jen po checklistu)"
mkdir -p www
for d in "${DIRS[@]:-}"; do
  [ -d "$d" ] || continue
  mkdir -p "www/$d"
  # Bez --delete defaultně bezpečnější; odkomentuj delete až po dry-run zvyku
  rsync -a "$d/" "www/$d/"
  echo "synced $d"
done
if [ -d presentace ]; then
  mkdir -p www/presentace
  rsync -a presentace/ www/presentace/
  echo "synced presentace"
fi
if [ -d shared ]; then
  mkdir -p www/shared
  rsync -a shared/ www/shared/
fi
if [ -d flow ]; then
  bash deploy/pre-deploy-check.sh flow || true
  mkdir -p www/flow
  rsync -a flow/ www/flow/
  echo "synced flow"
fi
if [ -d partner ]; then
  bash deploy/pre-deploy-check.sh partner || true
  mkdir -p www/partner
  rsync -a partner/ www/partner/
  echo "synced partner"
fi

echo "### 5) API / služby"
docker compose up -d --build
docker compose exec -T api python manage.py migrate --noinput

echo "### 6) Smoke"
curl -sS -o /dev/null -w "api_health:%{http_code}\n" "https://api.ulovklienty.cz/health/" || true
curl -sS -o /dev/null -w "hub:%{http_code}\n" "https://ulovklienty.cz/" || true

echo "=== Hotovo SHA=$GIT_SHA. Doporučeno: git tag live-$STAMP && git push origin live-$STAMP ==="
echo "Rollback: bash deploy/rollback-live.sh <tag|stamp>"
