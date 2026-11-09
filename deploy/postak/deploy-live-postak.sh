#!/usr/bin/env bash
# LIVE Pošťák — jen po schválení. Nepoužívat rsync --delete na www.
#
#   bash deploy/postak/deploy-live-postak.sh origin/main
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REF="${1:-origin/main}"
POSTAK_DIR="$ROOT/postak"
ENV_FILE="$POSTAK_DIR/.env.live"

cd "$ROOT"
git fetch origin 2>/dev/null || true
git checkout --force -B deploy-postak-live "$REF"
git reset --hard "$REF"
echo "GIT=$(git rev-parse --short HEAD)"

if [ ! -f "$ENV_FILE" ]; then
  echo "FAIL: chybí $ENV_FILE — spusťte bootstrap-live-env.sh"
  exit 1
fi

if ! docker network inspect ulov_default >/dev/null 2>&1; then
  echo "FAIL: síť ulov_default neexistuje"
  exit 1
fi

docker compose -p postak-live -f "$POSTAK_DIR/docker-compose.live.yml" --env-file "$ENV_FILE" up -d --build
docker compose -p postak-live -f "$POSTAK_DIR/docker-compose.live.yml" --env-file "$ENV_FILE" exec -T web \
  python manage.py migrate --noinput
docker compose -p postak-live -f "$POSTAK_DIR/docker-compose.live.yml" --env-file "$ENV_FILE" exec -T web \
  python manage.py postak_bunny_smoke || echo "WARN: Bunny smoke"

curl -fsS -o /dev/null -w "postak_prihlaseni=%{http_code}\n" \
  "https://www.ulovklienty.cz/postak/prihlaseni/" || echo "WARN: curl LIVE"

echo "OK: postak-live / ulov-live-postak"
