# Pošťák STAGING — ochrana proti LIVE CRM API

## Povinné v `.env` (staging kontejner)

- `POSTAK_STAGING_MODE=1`
- `MODERNIK_API_BASE=https://api-staging.ulovklienty.cz/partner-admin/api/postak/v1`
- `HYA_API_BASE=https://staging.hereyouare.cz/internal/postak/v1`

## Chování

1. Při startu Django: `assert_staging_crm_targets()` — špatná LIVE URL → proces skončí (`ImproperlyConfigured`).
2. Před každým CRM **zápisem** (POST/PATCH/PUT/DELETE): `block_live_crm_write()` — stejná ochrana ještě před HTTP.

GET/HEAD za běžného provozu se na LIVE v STAGING režimu **nespouští**, pokud je v `.env` stále LIVE base (start selže).

## Testy

`python manage.py test jadro.tests_staging_api_guard`

## Incident 2026-11-17

Špatné `MODERNIK_API_BASE` / `HYA_API_BASE` v postak staging `.env` → E2E zapisovalo na LIVE Moderník. Po opravě URL + tento guard.