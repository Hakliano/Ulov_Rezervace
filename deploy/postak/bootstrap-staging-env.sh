#!/usr/bin/env bash
# Jednorázové vytvoření postak/.env na serveru (žádný výpis secrets).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
POSTAK_DIR="$ROOT/postak"
ENV_FILE="$POSTAK_DIR/.env"
STAGING_ENV="$ROOT/.env.staging"

if [ -f "$ENV_FILE" ]; then
  echo "postak/.env already exists — skipped."
  exit 0
fi

if [ ! -f "$POSTAK_DIR/.env.staging.example" ]; then
  echo "FAIL: missing postak/.env.staging.example"
  exit 1
fi

if [ ! -f "$STAGING_ENV" ]; then
  echo "FAIL: missing .env.staging at repo root"
  exit 1
fi

TOKEN=""
if grep -q '^POSTAK_POTENCIALNI_API_TOKEN=' "$STAGING_ENV"; then
  TOKEN=$(grep '^POSTAK_POTENCIALNI_API_TOKEN=' "$STAGING_ENV" | cut -d= -f2- | tr -d '\r')
else
  TOKEN=$(openssl rand -hex 24)
  echo "POSTAK_POTENCIALNI_API_TOKEN=$TOKEN" >> "$STAGING_ENV"
fi

BUNNY_KEY=$(grep '^BUNNY_STORAGE_API_KEY=' "$STAGING_ENV" | cut -d= -f2- | tr -d '\r' || true)
if [ -z "$BUNNY_KEY" ]; then
  echo "WARN: BUNNY_STORAGE_API_KEY empty in .env.staging — Bunny disabled until fixed."
fi

SECRET_KEY=$(openssl rand -hex 32)
PG_PASS=$(openssl rand -hex 20)
MAIL_KEY=$(python3 -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())")

cp "$POSTAK_DIR/.env.staging.example" "$ENV_FILE"
chmod 600 "$ENV_FILE"

escape_sed() { printf '%s' "$1" | sed -e 's/[\/&]/\\&/g'; }

sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$(escape_sed "$SECRET_KEY")/" "$ENV_FILE"
sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(escape_sed "$PG_PASS")/" "$ENV_FILE"
sed -i "s/^POSTAK_MAIL_ENCRYPTION_KEY=.*/POSTAK_MAIL_ENCRYPTION_KEY=$(escape_sed "$MAIL_KEY")/" "$ENV_FILE"
sed -i "s/^MODERNIK_API_TOKEN=.*/MODERNIK_API_TOKEN=$(escape_sed "$TOKEN")/" "$ENV_FILE"
if [ -n "$BUNNY_KEY" ]; then
  sed -i "s/^POSTAK_BUNNY_ACCESS_KEY=.*/POSTAK_BUNNY_ACCESS_KEY=$(escape_sed "$BUNNY_KEY")/" "$ENV_FILE"
else
  sed -i "s/^POSTAK_BUNNY_ENABLED=.*/POSTAK_BUNNY_ENABLED=false/" "$ENV_FILE"
fi

echo "Created postak/.env (chmod 600). STAGING Postak API token synced with .env.staging."
