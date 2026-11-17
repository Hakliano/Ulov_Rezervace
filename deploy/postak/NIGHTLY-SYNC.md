# Noční synchronizace Pošťák (Moderník / HYA → cache)

## Chování

- **02:15 Europe/Prague** — `sync_modernik_klienti` (= stejná logika jako POST `/postak/klienti/sync/modernik/`, včetně `bootstrap_if_empty`).
- **03:30 Europe/Prague** — `sync_hya_klienti` (= POST `/postak/klienti/sync/hya/`).
- Žádný sync při návštěvě seznamu klientů.
- **Bez mazání** kontaktů z cache; jen delta/merge jako u ručních tlačítek.
- **Bez zápisu** do CRM Moderník/HYA (jen čtení API).

## Ochrana proti souběhu

1. Host `flock` v `/etc/cron.d/postak-live-sync`.
2. `jadro.sync_lock.sync_file_lock` uvnitř manage.py i ručních POST handlerů.

## LIVE instalace cronu

Na VPS (repo typicky `/opt/ulov`):

```bash
bash deploy/postak/install-postak-live-sync-cron.sh
```

Smoke (nevolat v produkční špičce — pouze ověří, že příkaz existuje):

```bash
docker exec -w /app ulov-live-postak python manage.py help sync_modernik_klienti
```

Logy: `/var/log/postak-sync-modernik.log`, `/var/log/postak-sync-hya.log`.