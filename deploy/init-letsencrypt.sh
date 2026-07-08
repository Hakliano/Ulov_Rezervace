#!/usr/bin/env bash
# Prvotní vydání Let's Encrypt certifikátu pro Nginx (webroot metoda).
# Spustit JEDNOU po `docker compose up -d db api` a po nasměrování DNS na server.
#
#   DOMAIN=api.vase-domena.cz EMAIL=vas@email.cz bash deploy/init-letsencrypt.sh
#
# STAGING=1 pro test (nezapočítává se do limitů Let's Encrypt).
set -euo pipefail

DOMAIN="${DOMAIN:-api.vase-domena.cz}"
EMAIL="${EMAIL:-}"
STAGING="${STAGING:-0}"

if [ -z "$EMAIL" ]; then
  echo "Nastavte EMAIL=vas@email.cz (pro upozornění na expiraci)." >&2
  exit 1
fi

CONF="./deploy/certbot/conf"
WWW="./deploy/certbot/www"
LIVE="$CONF/live/$DOMAIN"
mkdir -p "$CONF" "$WWW" "$LIVE"

# 1) Dočasný self-signed certifikát, aby Nginx vůbec nastartoval s HTTPS blokem.
if [ ! -f "$LIVE/fullchain.pem" ]; then
  echo "### Vytvářím dočasný self-signed certifikát ..."
  docker run --rm \
    -v "$(pwd)/deploy/certbot/conf:/etc/letsencrypt" \
    --entrypoint openssl certbot/certbot \
    req -x509 -nodes -newkey rsa:2048 -days 1 \
      -keyout "/etc/letsencrypt/live/$DOMAIN/privkey.pem" \
      -out "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" \
      -subj "/CN=$DOMAIN"
fi

echo "### Startuji Nginx ..."
docker compose up -d nginx

# 2) Smazat dočasný certifikát a vyžádat ostrý přes webroot.
echo "### Odstraňuji dočasný certifikát a žádám o ostrý pro $DOMAIN ..."
rm -rf "$CONF/live/$DOMAIN" "$CONF/archive/$DOMAIN" "$CONF/renewal/$DOMAIN.conf"

staging_arg=""
[ "$STAGING" != "0" ] && staging_arg="--staging"

docker run --rm \
  -v "$(pwd)/deploy/certbot/conf:/etc/letsencrypt" \
  -v "$(pwd)/deploy/certbot/www:/var/www/certbot" \
  certbot/certbot certonly --webroot -w /var/www/certbot \
    $staging_arg \
    --email "$EMAIL" \
    -d "$DOMAIN" \
    --rsa-key-size 4096 \
    --agree-tos \
    --non-interactive \
    --force-renewal

echo "### Reload Nginx ..."
docker compose exec nginx nginx -s reload || docker compose restart nginx

echo "### Hotovo. Certifikát pro $DOMAIN je aktivní."
echo "### Automatická obnova běží ve službě 'certbot' (docker compose up -d)."
