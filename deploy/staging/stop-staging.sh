#!/usr/bin/env bash
# Vypne STAGING kontejnery. Volumes, databáze a soubory zůstávají.
# Nespouštět na LIVE. Sdílený nginx/certbot se nevypíná.
set -euo pipefail

ROOT="${ULOV_ROOT:-/opt/ulov}"

stop_compose() {
  local project="$1"
  local file="$2"
  local envfile="${3:-}"
  if [ ! -f "$file" ]; then
    echo "SKIP: chybí $file"
    return 0
  fi
  if [ -n "$envfile" ] && [ -f "$envfile" ]; then
    docker compose -p "$project" -f "$file" --env-file "$envfile" stop
  else
    docker compose -p "$project" -f "$file" stop
  fi
  echo "STOPPED $project"
}

echo "### Ulov staging (API, worker, Materiálník, DB, Redis)"
stop_compose ulov-staging "$ROOT/docker-compose.staging.yml" "$ROOT/.env.staging"

echo "### Pošťák staging"
stop_compose postak-staging "$ROOT/postak/docker-compose.staging.yml" "$ROOT/postak/.env"

echo "### HYA staging"
HYA_DIR=""
if [ -d /opt/hya-staging ]; then
  HYA_DIR=/opt/hya-staging
fi
if [ -z "$HYA_DIR" ]; then
  HYA_DIR=$(docker inspect hya-staging-web --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' 2>/dev/null || true)
fi
if [ -n "$HYA_DIR" ] && [ -f "$HYA_DIR/docker-compose.yml" ]; then
  stop_compose hya-staging "$HYA_DIR/docker-compose.yml" "$HYA_DIR/.env"
elif [ -n "$HYA_DIR" ] && [ -f "$HYA_DIR/compose.yml" ]; then
  stop_compose hya-staging "$HYA_DIR/compose.yml" "$HYA_DIR/.env"
else
  echo "SKIP: HYA staging compose nenalezen"
fi

echo "### Stav (mají zůstat Exited, volumes beze změny)"
docker ps -a --filter name=staging --format '{{.Names}} {{.Status}}'
echo "STOP staging hotovo. Zapnutí: bash deploy/staging/start-staging.sh"
