#!/usr/bin/env bash
# První / opakované nasazení Pošťáka na Hetzner STAGING (jen DEV git, samostatný compose).
# Nespouštět na LIVE. Neupravuje hlavní deploy-staging.sh (ULOV API).
#
#   bash deploy/postak/deploy-staging-postak.sh origin/dev
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REF="${1:-origin/dev}"
POSTAK_DIR="$ROOT/postak"

cd "$ROOT"
git fetch origin 2>/dev/null || true
git checkout --force -B deploy-postak-staging "$REF"
git reset --hard "$REF"
echo "GIT=$(git rev-parse --short HEAD) FULL=$(git rev-parse HEAD)"

if [ ! -f "$POSTAK_DIR/.env" ]; then
  echo "FAIL: chybí $POSTAK_DIR/.env (zkopírujte z .env.staging.example na serveru)"
  exit 1
fi

if ! docker network inspect ulov_default >/dev/null 2>&1; then
  echo "FAIL: síť ulov_default neexistuje — nejdřív běží hlavní docker compose na serveru"
  exit 1
fi

echo "### Build & up"
docker compose -p postak-staging -f "$POSTAK_DIR/docker-compose.staging.yml" --env-file "$POSTAK_DIR/.env" up -d --build

echo "### Migrate"
docker compose -p postak-staging -f "$POSTAK_DIR/docker-compose.staging.yml" --env-file "$POSTAK_DIR/.env" exec -T web \
  python manage.py migrate --noinput

echo "### Bunny smoke (prefix postak/staging pouze)"
docker compose -p postak-staging -f "$POSTAK_DIR/docker-compose.staging.yml" --env-file "$POSTAK_DIR/.env" exec -T web \
  python manage.py postak_bunny_smoke || {
  echo "WARN: Bunny smoke selhal — zkontrolujte POSTAK_BUNNY_* v .env"
}

echo "### HTTP check (z hostu přes nginx)"
curl -fsS -o /dev/null -w "postak_prihlaseni=%{http_code}\n" \
  "https://www.staging.ulovklienty.cz/postak/prihlaseni/" || echo "WARN: curl selhal — nginx snippet ještě není nasazený?"

echo "OK: Pošťák staging compose běží jako postak-staging / ulov-staging-postak"
