#!/usr/bin/env bash
# Vystaví Let's Encrypt cert pro materialnik.cz (+ www + staging) a zapne HTTPS vhost.
set -euo pipefail
cd "$(dirname "$0")/.."

CONF_HTTP=deploy/nginx/conf.d/materialnik.conf
CONF_SSL=deploy/nginx/conf.d/materialnik-ssl.conf.pending
CONF_SSL_ON=deploy/nginx/conf.d/materialnik-ssl.conf

echo "=== 1) HTTP vhost musí existovat (ACME) ==="
if [ ! -f "$CONF_HTTP" ]; then
  echo "FAIL: chybí $CONF_HTTP"
  exit 1
fi

echo "=== 2) Certbot webroot ==="
docker compose run --rm --entrypoint certbot certbot certonly \
  --webroot -w /var/www/certbot \
  --cert-name materialnik.cz \
  --non-interactive --agree-tos \
  --email "${CERTBOT_EMAIL:-info@ulovklienty.cz}" \
  -d materialnik.cz \
  -d www.materialnik.cz \
  -d staging.materialnik.cz

echo "=== 3) Zapnout HTTPS vhost ==="
if [ ! -f "$CONF_SSL" ]; then
  echo "FAIL: chybí $CONF_SSL"
  exit 1
fi
cp -f "$CONF_SSL" "$CONF_SSL_ON"
rm -f "$CONF_HTTP"

docker compose exec -T nginx nginx -t
docker compose exec -T nginx nginx -s reload

echo "=== Smoke ==="
curl -sS -o /dev/null -w "staging_materialnik:%{http_code}\n" "https://staging.materialnik.cz/" || true
curl -sS -o /dev/null -w "www_materialnik:%{http_code}\n" "https://www.materialnik.cz/" || true
echo "=== Hotovo ==="
echo "Po certu: DNS A záznamy + tento skript. Prodejní web je presentace/materialnik/"
