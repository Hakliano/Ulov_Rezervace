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

# Po checkoutu znovu spusť skript z disku — jinak by běžela stará verze
# (inline heredoc / overrides z paměti před `git checkout`).
if [ "${STAGING_DEPLOY_REEXEC:-}" != "1" ] && [ "$REF" != "HEAD" ]; then
  export STAGING_DEPLOY_REEXEC=1
  exec bash "$ROOT/deploy/deploy-staging.sh" "$REF"
fi

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

# SMTP_ENCRYPTION_KEY: nikdy z LIVE. Persistentní staging sidecar, abort při shodě.
python3 "$ROOT/deploy/staging_smtp_encryption_key.py"
if [ ! -f .smtp_encryption_key.live ]; then
  echo "FAIL: chybí .smtp_encryption_key.live — nelze ověřit oddělení od LIVE"
  exit 1
fi
if cmp -s .smtp_encryption_key .smtp_encryption_key.live; then
  echo "FAIL: staging SMTP encryption sidecar matches LIVE"
  exit 1
fi

# Hosts / CORS (SMTP klíč už je v .env.staging ze sidecar)
python3 - <<'PY'
from pathlib import Path

p = Path(".env.staging")
text = p.read_text(encoding="utf-8")

lines = []
overrides = {
    "ALLOWED_HOSTS": "api-staging.ulovklienty.cz,staging.ulovklienty.cz,www.staging.ulovklienty.cz,localhost,127.0.0.1,ulov-staging-api,staging-api",
    "SECURE_SSL_REDIRECT": "false",
    "CORS_ALLOWED_ORIGINS": "https://www.staging.ulovklienty.cz,https://staging.ulovklienty.cz,https://demo1.staging.ulovklienty.cz,https://demo2.staging.ulovklienty.cz,https://demo3.staging.ulovklienty.cz,https://demo4.staging.ulovklienty.cz,https://demo5.staging.ulovklienty.cz,https://demo6.staging.ulovklienty.cz,https://demo7.staging.ulovklienty.cz,https://demo8.staging.ulovklienty.cz,https://staging.modernik.cz,https://www.modernik.cz,https://modernik.cz,https://staging.materialnik.cz,https://www.materialnik.cz,https://materialnik.cz",
    "CSRF_TRUSTED_ORIGINS": "https://www.staging.ulovklienty.cz,https://staging.ulovklienty.cz,https://api-staging.ulovklienty.cz",
    "SENTRY_ENVIRONMENT": "staging",
    "EMAIL_VIA_CELERY": "false",
    "FLOW_BASE_URL": "https://www.staging.ulovklienty.cz/flow/",
    "API_PUBLIC_BASE_URL": "https://api-staging.ulovklienty.cz/api",
    "CUSTOMER_CARD_CONFIRM_BASE_URL": "https://api-staging.ulovklienty.cz/api",
    "MATERIALNIK_URL": "http://ulov-staging-materialnik:8000",
    "MATERIALNIK_PUBLIC_URL": "https://www.staging.ulovklienty.cz/sklad",
    "MATERIALNIK_M2M_KEY": "staging-materialnik-m2m",
    "MATERIALNIK_STUB": "false",
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
    if k == "SMTP_ENCRYPTION_KEY":
        # Klíč už nastavil staging_smtp_encryption_key.py — nepřepisovat z LIVE.
        lines.append(line)
        keys_done.add(k)
        continue
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
if cmp -s .smtp_encryption_key .smtp_encryption_key.live; then
  echo "FAIL: staging SMTP encryption sidecar matches LIVE"
  exit 1
fi

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
if [ -d modernik ]; then
  bash deploy/pre-deploy-check.sh modernik || true
  mkdir -p www-staging/modernik
  rsync -a modernik/ www-staging/modernik/
fi
if [ -d shared ]; then
  mkdir -p www-staging/shared
  rsync -a shared/ www-staging/shared/
fi
if [ -d flow ]; then
  bash deploy/pre-deploy-check.sh flow || true
  mkdir -p www-staging/flow
  rsync -a flow/ www-staging/flow/
fi
if [ -d partner ]; then
  bash deploy/pre-deploy-check.sh partner || true
  mkdir -p www-staging/partner
  rsync -a partner/ www-staging/partner/
fi

# Frontendy musí volat staging API + dema pod staging hostem
find www-staging -type f \( -name '*.js' -o -name '*.html' \) -print0 \
  | xargs -0 sed -i \
    -e 's|https://api\.ulovklienty\.cz|https://api-staging.ulovklienty.cz|g' \
    -e 's|https://demo\([0-9]\)\.ulovklienty\.cz|https://www.staging.ulovklienty.cz/salon\1|g' \
    -e 's|https://www\.ulovklienty\.cz/|https://www.staging.ulovklienty.cz/|g' \
    -e 's|https://ulovklienty\.cz/|https://www.staging.ulovklienty.cz/|g' \
    -e 's|https://www\.modernik\.cz|https://staging.modernik.cz|g' \
    -e 's|https://modernik\.cz|https://staging.modernik.cz|g' \
    -e 's|https://www\.materialnik\.cz|https://staging.materialnik.cz|g' \
    -e 's|https://materialnik\.cz|https://staging.materialnik.cz|g' \
  || true

# Windows UTF-8 BOM rozbije <script> v prohlížeči (SyntaxError → věčné „Načítám…“)
python3 - <<'PY'
from pathlib import Path
bom = b"\xef\xbb\xbf"
n = 0
for p in Path("www-staging").rglob("*"):
    if p.suffix.lower() not in {".js", ".html", ".css"}:
        continue
    data = p.read_bytes()
    if data.startswith(bom):
        p.write_bytes(data[3:])
        n += 1
print(f"stripped UTF-8 BOM from {n} files")
PY

echo "### Start staging containers"
# Síť LIVE musí existovat
docker network inspect ulov_default >/dev/null

# Zachovej už nahraná media z běžícího kontejneru před mountem volume
mkdir -p media-staging
docker cp ulov-staging-api:/app/media/. media-staging/ 2>/dev/null || true

docker compose -p ulov-staging -f docker-compose.staging.yml --env-file .env.staging up -d --build staging-api db redis staging-materialnik worker

echo "### Migrate + seed (základní data, oddělená DB)"
# staging-api už migrate dělá při startu; druhý běh v souběhu umí DuplicateType
sleep 8
docker compose -p ulov-staging -f docker-compose.staging.yml --env-file .env.staging exec -T staging-api \
  python manage.py migrate --noinput || true
docker compose -p ulov-staging -f docker-compose.staging.yml --env-file .env.staging exec -T staging-api \
  python manage.py seed_salons 2>/dev/null || true
docker compose -p ulov-staging -f docker-compose.staging.yml --env-file .env.staging exec -T staging-api \
  python manage.py seed_vertical_demos 2>/dev/null || true
docker compose -p ulov-staging -f docker-compose.staging.yml --env-file .env.staging exec -T staging-api \
  python manage.py fix_pg_sequences 2>/dev/null || true

echo "### Reload LIVE nginx (staging vhost + mount www-staging)"
cp -f deploy/nginx/conf.d/staging.conf deploy/nginx/conf.d/staging.conf 2>/dev/null || true
mv -f deploy/nginx/conf.d/staging.conf.disabled deploy/nginx/conf.d/staging.conf 2>/dev/null || true
docker compose up -d nginx
docker compose exec -T nginx nginx -t
docker compose exec -T nginx nginx -s reload

echo "### SMTP encryption isolation (fingerprints only, never print keys)"
python3 - <<'PY'
from hashlib import sha256
from pathlib import Path
import sys

def fp(path):
    p = Path(path)
    if not p.is_file():
        return "missing"
    return sha256(p.read_text(encoding="utf-8").strip().encode()).hexdigest()[:12]

def env_key_fp(path):
    prefix = "SMTP_ENCRYPTION_KEY="
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return sha256(line[len(prefix):].strip().encode()).hexdigest()[:12]
    return "missing"

stg = fp(".smtp_encryption_key")
live = fp(".smtp_encryption_key.live")
envfp = env_key_fp(".env.staging")
print("sidecar_fp", stg)
print("live_fp", live)
print("env_fp", envfp)
if stg in {"", "missing"} or live in {"", "missing"} or stg == live:
    print("FAIL: staging SMTP key is not isolated from LIVE")
    sys.exit(1)
if envfp != stg:
    print("FAIL: .env.staging SMTP key does not match staging sidecar")
    sys.exit(1)
print("isolated yes")
PY
docker compose -p ulov-staging -f docker-compose.staging.yml --env-file .env.staging exec -T staging-api \
  python manage.py shell -c 'from hashlib import sha256; from django.conf import settings; k=(settings.SMTP_ENCRYPTION_KEY or "").strip(); print("api_fp", sha256(k.encode()).hexdigest()[:12] if k else "empty")'
docker compose -p ulov-staging -f docker-compose.staging.yml --env-file .env.staging exec -T worker \
  python manage.py shell -c 'from hashlib import sha256; from django.conf import settings; k=(settings.SMTP_ENCRYPTION_KEY or "").strip(); print("worker_fp", sha256(k.encode()).hexdigest()[:12] if k else "empty")'

echo "=== STAGING hotovo ==="
echo "Hub:  https://www.staging.ulovklienty.cz/"
echo "Moderník: https://staging.modernik.cz/ (po DNS + cert)"
echo "Materiálník app: https://www.staging.ulovklienty.cz/sklad/"
echo "API:  https://api-staging.ulovklienty.cz/health/"
echo "Demo: https://www.staging.ulovklienty.cz/salon1/"
echo "Maily jdou na EMAIL_OVERRIDE_TO (viz .env.staging) — ne ostrým zákazníkům."
echo
echo "DNS: www.staging / staging / api-staging → IP serveru (OK pokud resolve)"
echo "Cert: bash deploy/expand-staging-cert.sh"
