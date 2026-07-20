#!/usr/bin/env bash
# Rozšíří cert ulovklienty.cz o staging hosty (vyžaduje DNS A záznamy).
set -euo pipefail
cd "$(dirname "$0")/.."

DOMAINS=(
  ulovklienty.cz
  www.ulovklienty.cz
  staging.ulovklienty.cz
  www.staging.ulovklienty.cz
  api-staging.ulovklienty.cz
  demo1.ulovklienty.cz
  demo2.ulovklienty.cz
  demo3.ulovklienty.cz
  demo4.ulovklienty.cz
  demo5.ulovklienty.cz
  demo6.ulovklienty.cz
  demo7.ulovklienty.cz
  demo8.ulovklienty.cz
)

ARGS=()
for d in "${DOMAINS[@]}"; do
  ARGS+=(-d "$d")
done

docker compose run --rm --entrypoint certbot certbot certonly \
  --webroot -w /var/www/certbot \
  --cert-name ulovklienty.cz \
  --expand \
  --non-interactive --agree-tos \
  --email "${CERTBOT_EMAIL:-info@ulovklienty.cz}" \
  "${ARGS[@]}"

docker compose exec -T nginx nginx -s reload
echo "Cert expanded + nginx reloaded."
