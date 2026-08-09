#!/usr/bin/env bash
# Vystaví Let's Encrypt cert pro franek-autoservis.cloud a zapne HTTPS vhost.
# Předpoklad: DNS A apex (+ www přes *) → IP tohoto serveru.
set -euo pipefail
cd "$(dirname "$0")/.."

DOMAIN=franek-autoservis.cloud
WWW=www.franek-autoservis.cloud
CONF_FULL=deploy/nginx/conf.d/partner-franek.conf
CONF_HTTP=deploy/nginx/conf.d/partner-franek-http-only.conf

echo "=== 1) Dočasný HTTP-only vhost (ACME; bez SSL souborů) ==="
cat > "$CONF_HTTP" <<EOF
# Dočasný — smaže issue-partner-franek-cert.sh po vystavení certu
server {
    listen 80;
    server_name ${DOMAIN} ${WWW};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        root /var/www/sites/provoz-franek;
        index index.html;
        try_files \$uri \$uri/ =404;
    }
}
EOF

# Plný conf odlož, dokud není cert (jinak nginx -t padne)
if [ -f "$CONF_FULL" ]; then
  mv -f "$CONF_FULL" "${CONF_FULL}.pending"
fi

docker compose exec -T nginx nginx -t
docker compose exec -T nginx nginx -s reload

echo "=== 2) Certbot webroot ==="
docker compose run --rm --entrypoint certbot certbot certonly \
  --webroot -w /var/www/certbot \
  --cert-name "$DOMAIN" \
  --non-interactive --agree-tos \
  --email "${CERTBOT_EMAIL:-info@ulovklienty.cz}" \
  -d "$DOMAIN" \
  -d "$WWW"

echo "=== 3) Zapnout plný HTTPS conf ==="
if [ -f "${CONF_FULL}.pending" ]; then
  mv -f "${CONF_FULL}.pending" "$CONF_FULL"
fi
rm -f "$CONF_HTTP"

docker compose exec -T nginx nginx -t
docker compose exec -T nginx nginx -s reload
echo "=== Hotovo: https://${DOMAIN}/ a https://${WWW}/ ==="
