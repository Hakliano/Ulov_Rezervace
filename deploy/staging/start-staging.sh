#!/usr/bin/env bash
# Zapne STAGING bez rebuildu a bez mazání volumes.
set -euo pipefail

ROOT="${ULOV_ROOT:-/opt/ulov}"

start_compose() {
  local project="$1"
  local file="$2"
  local envfile="${3:-}"
  if [ ! -f "$file" ]; then
    echo "SKIP: chybí $file"
    return 0
  fi
  if [ -n "$envfile" ] && [ -f "$envfile" ]; then
    docker compose -p "$project" -f "$file" --env-file "$envfile" up -d
  else
    docker compose -p "$project" -f "$file" up -d
  fi
  echo "STARTED $project"
}

echo "### Ulov staging"
start_compose ulov-staging "$ROOT/docker-compose.staging.yml" "$ROOT/.env.staging"

echo "### Pošťák staging"
start_compose postak-staging "$ROOT/postak/docker-compose.staging.yml" "$ROOT/postak/.env"

echo "### HYA staging"
HYA_DIR=""
if [ -d /opt/hya-staging ]; then
  HYA_DIR=/opt/hya-staging
fi
if [ -z "$HYA_DIR" ]; then
  HYA_DIR=$(docker inspect hya-staging-web --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' 2>/dev/null || true)
fi
if [ -n "$HYA_DIR" ] && [ -f "$HYA_DIR/docker-compose.yml" ]; then
  start_compose hya-staging "$HYA_DIR/docker-compose.yml" "$HYA_DIR/.env"
elif [ -n "$HYA_DIR" ] && [ -f "$HYA_DIR/compose.yml" ]; then
  start_compose hya-staging "$HYA_DIR/compose.yml" "$HYA_DIR/.env"
else
  echo "SKIP: HYA staging compose nenalezen"
fi

docker ps --filter name=staging --format '{{.Names}} {{.Status}}'
echo "START staging hotovo."
