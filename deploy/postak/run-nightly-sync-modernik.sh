#!/usr/bin/env bash
# Voláno z cronu pod flock; v kontejneru druhý zámek v manage.py.
set -euo pipefail
exec docker exec -w /app ulov-live-postak python manage.py sync_modernik_klienti