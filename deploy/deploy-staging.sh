#!/usr/bin/env bash
# Nasazení / aktualizace STAGING z aktuálního git stromu na serveru.
# Oddělená DB. Maily → EMAIL_OVERRIDE_TO.
#
#   bash deploy/deploy-staging.sh              # default: origin/dev
#   bash deploy/deploy-staging.sh origin/dev
#
set -euo pipefail

cd "$(dirname "$0")/.."
REF="${1:-origin/dev}"
ROOT="$(pwd)"

echo "=== STAGING deploy z GitHub DEV (ref=$REF) ==="

git fetch origin --tags 2>/dev/null || true
if [ "$REF" != "HEAD" ]; then
  git checkout --force -B deploy-staging "$REF"
  git reset --hard "$REF"
fi
echo "GIT=$(git rev-parse --short HEAD)"

if [ ! -f .env ]; then
  echo "FAIL: chybí .env (LIVE) — z něj se odvodí .env.staging"
  exit 1
fi

echo "### .env.staging"
# Základ z LIVE env, přepisy pro staging (nesahá na LIVE .env)
cp -a .env .env.staging
# DB jméno/volume jsou oddělené přes compose; v .env musí sedět DB_NAME
sed -i 's/^DB_NAME=.*/DB_NAME=ulov_staging/' .env.staging || true
grep -q '^DB_NAME=' .env.staging || echo 'DB_NAME=ulov_staging' >> .env.staging

# Hosts / CORS
python3 - <<'PY'
from pathlib import Path
p = Path(".env.staging")
text = p.read_text(encoding="utf-8")
lines = []
overrides = {
    "ALLOWED_HOSTS": "api-staging.ulovklienty.cz,staging.ulovklienty.cz,www.staging.ulovklienty.cz,localhost",
    "CORS_ALLOWED_ORIGINS": "https://www.staging.ulovklienty.cz,https://staging.ulovklienty.cz,https://demo1.staging.ulovklienty.cz,https://demo2.staging.ulovklienty.cz,https://demo3.staging.ulovklienty.cz,https://demo4.staging.ulovklienty.cz,https://demo5.staging.ulovklienty.cz,https://demo6.staging.ulovklienty.cz,https://demo7.staging.ulovklienty.cz,https://demo8.staging.ulovklienty.cz",
    "CSRF_TRUSTED_ORIGINS": "https://www.staging.ulovklienty.cz,https://staging.ulovklienty.cz,https://api-staging.ulovklienty.cz",
    "SENTRY_ENVIRONMENT": "staging",
    "EMAIL_VIA_CELERY": "false",
}
# EMAIL_OVERRIDE_TO — zachovej pokud už je, jinak info@
if "EMAIL_OVERRIDE_TO=" not in text:
    overrides["EMAIL_OVERRIDE_TO"] = "info@ulovklienty.cz"

keys_done = set()
for line in text.splitlines():
    if not line.strip() or line.strip().startswith("#") or "=" not in line:
        lines.append(line)
        continue
    k, _, v = line.partition("=")
    k = k.strip()
    if k in overrides:
        lines.append(f"{k}={overrides[k]}")
        keys_done.add(k)
    else:
        lines.append(line)
for k, v in overrides.items():
    if k not in keys_done:
        lines.append(f"{k}={v}")
p.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("env.staging ok")
PY

echo "### Sync statiky → www-staging (+ API na api-staging)"
mkdir -p www-staging
mapfile -t DIRS < <(find . -maxdepth 1 -type d \( -name 'salon*' -o -name 'zdravi-*' -o -name 'remesla-*' -o -name 'provoz-*' \) -printf '%f\n' | sort)
if [ "${#DIRS[@]}" -gt 0 ]; then
  bash deploy/pre-deploy-check.sh "${DIRS[@]}" || {
    echo "WARN: některé složky neúplné — syncnu jen OK (salon7/8 bez index přeskoč)"
  }
fi
for d in "${DIRS[@]:-}"; do
  [ -d "$d" ] || continue
  if [ ! -f "$d/index.html" ]; then
    echo "SKIP incomplete $d"
    continue
  fi
  mkdir -p "www-staging/$d"
  rsync -a "$d/" "www-staging/$d/"
done
if [ -d presentace ]; then
  mkdir -p www-staging/presentace
  rsync -a presentace/ www-staging/presentace/
fi
if [ -d shared ]; then
  mkdir -p www-staging/shared
  rsync -a shared/ www-staging/shared/
fi

# Frontendy musí volat staging API + dema pod staging hostem
find www-staging -type f \( -name '*.js' -o -name '*.html' \) -print0 \
  | xargs -0 sed -i \
    -e 's|https://api\.ulovklienty\.cz|https://api-staging.ulovklienty.cz|g' \
    -e 's|https://demo\([0-9]\)\.ulovklienty\.cz|https://www.staging.ulovklienty.cz/salon\1|g' \
    -e 's|https://www\.ulovklienty\.cz/|https://www.staging.ulovklienty.cz/|g' \
    -e 's|https://ulovklienty\.cz/|https://www.staging.ulovklienty.cz/|g' \
  || true

echo "### Start staging containers"
# Síť LIVE musí existovat
docker network inspect ulov_default >/dev/null

docker compose -p ulov-staging -f docker-compose.staging.yml --env-file .env.staging up -d --build api db redis

echo "### Migrate + seed (základní data, oddělená DB)"
docker compose -p ulov-staging -f docker-compose.staging.yml --env-file .env.staging exec -T api \
  python manage.py migrate --noinput
docker compose -p ulov-staging -f docker-compose.staging.yml --env-file .env.staging exec -T api \
  python manage.py seed_salons 2>/dev/null || true
docker compose -p ulov-staging -f docker-compose.staging.yml --env-file .env.staging exec -T api \
  python manage.py seed_vertical_demos 2>/dev/null || true

echo "### Reload LIVE nginx (staging vhost + mount www-staging)"
cp -f deploy/nginx/conf.d/staging.conf deploy/nginx/conf.d/staging.conf 2>/dev/null || true
mv -f deploy/nginx/conf.d/staging.conf.disabled deploy/nginx/conf.d/staging.conf 2>/dev/null || true
docker compose up -d nginx
docker compose exec -T nginx nginx -t
docker compose exec -T nginx nginx -s reload

echo "=== STAGING hotovo ==="
echo "Hub:  https://www.staging.ulovklienty.cz/"
echo "API:  https://api-staging.ulovklienty.cz/health/"
echo "Demo: https://www.staging.ulovklienty.cz/salon1/"
echo "Maily jdou na EMAIL_OVERRIDE_TO (viz .env.staging) — ne ostrým zákazníkům."
echo
echo "DNS: www.staging / staging / api-staging → IP serveru (OK pokud resolve)"
echo "Cert: bash deploy/expand-staging-cert.sh"
