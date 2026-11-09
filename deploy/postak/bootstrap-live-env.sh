#!/usr/bin/env bash
# Jednorázové vytvoření postak/.env.live (používá se jako --env-file při deployi LIVE).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
POSTAK_DIR="$ROOT/postak"
ENV_FILE="$POSTAK_DIR/.env.live"
LIVE_ENV="$ROOT/.env"
STAGING_TEMPLATE="$POSTAK_DIR/.env.live.example"

if [ -f "$ENV_FILE" ]; then
  echo "postak/.env.live already exists — skipped."
  exit 0
fi

if [ ! -f "$STAGING_TEMPLATE" ]; then
  echo "FAIL: missing .env.live.example"
  exit 1
fi

BUNNY_KEY=""
if [ -f "$LIVE_ENV" ]; then
  BUNNY_KEY=$(grep '^BUNNY_STORAGE_API_KEY=' "$LIVE_ENV" | cut -d= -f2- | tr -d '\r' || true)
fi
if [ -z "$BUNNY_KEY" ] && [ -f "$ROOT/.env.staging" ]; then
  BUNNY_KEY=$(grep '^BUNNY_STORAGE_API_KEY=' "$ROOT/.env.staging" | cut -d= -f2- | tr -d '\r' || true)
fi

TOKEN=""
if [ -f "$LIVE_ENV" ] && grep -q '^POSTAK_POTENCIALNI_API_TOKEN=' "$LIVE_ENV"; then
  TOKEN=$(grep '^POSTAK_POTENCIALNI_API_TOKEN=' "$LIVE_ENV" | cut -d= -f2- | tr -d '\r')
else
  TOKEN=$(openssl rand -hex 24)
  if [ -f "$LIVE_ENV" ]; then
    echo "POSTAK_POTENCIALNI_API_TOKEN=$TOKEN" >> "$LIVE_ENV"
  fi
fi

SECRET_KEY=$(openssl rand -hex 32)
PG_PASS=$(openssl rand -hex 20)
MAIL_KEY=$(python3 -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())")

cp "$STAGING_TEMPLATE" "$ENV_FILE"
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

echo "Created postak/.env.live (chmod 600)."
