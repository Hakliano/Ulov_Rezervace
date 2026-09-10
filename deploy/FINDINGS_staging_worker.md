# Nález: `deploy-staging.sh` nespouští Celery worker

**Stav:** otevřený, mimo P0.3 LIVE deploy (neopravovat v rámci tohoto nasazení).
**Zaznamenáno:** 2026-09-10 při ověření P0.3 na stagingu.

## Symptom

`docker-compose.staging.yml` službu `worker` definuje, ale `deploy/deploy-staging.sh` ji po buildu **nenastartuje**.

Po běžném staging deployi běží typicky jen `staging-api`, `db`, `redis`, `staging-materialnik`. `ulov-staging-worker` chybí, dokud ho někdo nespustí ručně.

Důsledek: `task_email_test.delay()` (a ostatní Celery e-maily) zůstanou ve frontě Redis, dokud worker neběží.

P0.3 staging řetězec proto worker jednorázově nastartoval mimo skript. LIVE compose worker spouští (`docker compose up -d --build` v `deploy-live.sh`).

## Co opravit později

1. V `deploy-staging.sh` po API startu přidat `worker` do `docker compose … up -d`.
2. Ověřit, že worker dostane stejné `.env.staging` (včetně `SMTP_ENCRYPTION_KEY` ze sidecar `.smtp_encryption_key`).
3. Smoke: `task_email_test.delay` po čistém staging deployi, bez ručního `up worker`.

Související (také neřešit v tomto LIVE deployi): staging skript kopíruje LIVE `.env` do `.env.staging` a `SMTP_ENCRYPTION_KEY` z té kopie bere **dřív** než ze sidecar. Po P0.3 má LIVE vlastní klíč v `.env`; příští staging deploy by ho mohl zapsat do staging sidecar. Do opravy pořadí (preferovat `.smtp_encryption_key`) staging deploy nespouštět, nebo sidecar předem zálohovat.
