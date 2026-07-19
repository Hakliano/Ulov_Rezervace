# Runbook — Redis + fronta e-mailů (Celery)

## Co běží

| Služba | Role |
|--------|------|
| `redis` | Sdílená cache (throttling) + fronta úloh |
| `api` | Gunicorn / Django |
| `worker` | Celery — odesílá e-maily z fronty |
| `cron` | Životní cyklus; při `EMAIL_VIA_CELERY=true` jen zařazuje maily |

## Health endpoint (monitoring)

```bash
curl -s https://api.ulovklienty.cz/health/
```

Očekávaná odpověď (ostrý provoz s frontou):

```json
{
  "status": "ok",
  "database": "ok",
  "redis": "ok",
  "celery_queue": "ok",
  "celery_queue_depth": 0,
  "email_via_celery": true
}
```

| Pole | Význam |
|------|--------|
| `status` | `ok` / `error` — DB + Redis (pro Uptime Kuma / HTTP check) |
| `celery_queue_depth` | kolik mailových úloh čeká ve frontě |
| `celery_queue` | `ok` nebo `backlog:N` (N ≥ 50) — **nehází 503**, jen signál |
| `email_via_celery` | jestli API posílá maily do fronty |

### Uptime monitor (doporučeno)

Externí služba (Uptime Kuma, Better Stack, Hetrix…) na:

- URL: `https://api.ulovklienty.cz/health/`
- očekávaný status: **200**
- interval: 1–5 minut

Při 503 přijde alert (padlá DB nebo Redis). Rostoucí `celery_queue_depth` sledujte občas ručně / v logu — není to HTTP alarm.

## Zapnutí fronty (ostré)

1. V `.env`:
   ```
   REDIS_URL=redis://redis:6379/0
   EMAIL_VIA_CELERY=true
   ```
2. `docker compose up -d --build`
3. Ověřit health + `docker compose logs -f worker`
4. Na demu rezervace → task ve worker logu → e-mail dorazí

Testovací e-mail z adminu (`email_test`) jde **vždy sync** (diagnostika SMTP).

## Nouzový rollback (maily nechodí / worker mrtvý)

1. V `.env`: `EMAIL_VIA_CELERY=false`
2. `docker compose up -d api cron`
3. Maily znovu sync (jako dřív)
4. Worker můžete nechat vypnutý, dokud neopravíte problém

## Diagnostika — „maily nechodí“

```bash
cd /opt/ulov

# 1) Health
curl -s https://api.ulovklienty.cz/health/

# 2) Běží worker?
docker compose ps worker
docker compose logs --tail=100 worker

# 3) Redis
docker compose exec redis redis-cli ping
docker compose exec redis redis-cli llen celery

# 4) Po změně .env / recreate api — nginx občas 502
docker compose restart nginx
```

Rozhodovací strom:

| Příznak | Akce |
|---------|------|
| rezervace OK, e-mail nejde, worker log ticho | `EMAIL_VIA_CELERY`? worker běží? |
| task v logu, SMTP chyba | heslo / Forpsi / `email_test` z adminu |
| `celery_queue_depth` roste | worker mrtvý nebo SMTP hang → rollback na sync |
| `/health/` 503 `redis` | `docker compose up -d redis` |
| 502 Bad Gateway po deployi | `docker compose restart nginx` |

## Lokální vývoj

Bez Redis: prázdné `REDIS_URL`, `EMAIL_VIA_CELERY=false` → LocMem + sync maily.
