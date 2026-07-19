# Runbook — Redis + fronta e-mailů (Celery)

## Co běží

| Služba | Role |
|--------|------|
| `redis` | Sdílená cache (throttling) + fronta úloh |
| `api` | Gunicorn / Django |
| `worker` | Celery — odesílá e-maily z fronty |
| `cron` | Životní cyklus; při `EMAIL_VIA_CELERY=true` jen zařazuje maily |

## Zapnutí fronty (ostré)

1. V `.env` musí být:
   ```
   REDIS_URL=redis://redis:6379/0
   EMAIL_VIA_CELERY=true
   ```
2. `docker compose up -d --build`
3. Ověřit:
   ```
   curl -s https://api.ulovklienty.cz/health/
   docker compose logs -f worker
   ```
4. Na demu vytvořit rezervaci → v logu workeru task → e-mail dorazí.

Testovací e-mail z adminu (`email_test`) jde **vždy sync** (diagnostika SMTP).

## Nouzový rollback (maily nechodí / worker mrtvý)

1. V `.env` nastavit `EMAIL_VIA_CELERY=false`
2. `docker compose up -d api cron` (restart api+cron stačí)
3. Maily jdou znovu synchronně v requestu / cronu jako dřív.
4. Worker může zůstat vypnutý, dokud neopravíte problém.

## Diagnostika

```bash
# Health (DB + Redis)
curl -s https://api.ulovklienty.cz/health/

# Žije worker?
docker compose ps worker
docker compose logs --tail=100 worker

# Redis
docker compose exec redis redis-cli ping
```

Typické příznaky:
- rezervace OK, e-mail nejde → worker / Redis / SMTP hesla
- `/health/` 503 na redis → Redis kontejner
- po deployi maily ticho → zapomněli jste `EMAIL_VIA_CELERY=true` nebo worker neběží

## Lokální vývoj

Bez Redis: nechte `REDIS_URL` prázdné a `EMAIL_VIA_CELERY=false` → LocMem + sync maily.
