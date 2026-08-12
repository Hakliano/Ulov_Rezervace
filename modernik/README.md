# Moderník — lokální vývoj

Prodejní web produktu **Moderník** (projekt ULOV KLIENTY).

## Lokální náhled

Z kořene repozitáře:

```bash
python -m http.server 8080
```

- Hub ULOV: http://localhost:8080/presentace/
- Moderník: http://localhost:8080/modernik/

Formuláře volají API na `localhost:8000` — spusťte backend, nebo testujte odeslání až na stagingu.

## Staging / LIVE (až po DNS)

| Prostředí | URL |
|---|---|
| Staging | `https://staging.modernik.cz` |
| LIVE | `https://www.modernik.cz` |

Deploy: složka `modernik/` se syncuje z `deploy/deploy-staging.sh` / `deploy/deploy-live.sh`.

## Branding

- Logo: zatím textové wordmarky (`MODERNÍK`) — nahradit finálním logem na CDN.
- Právní dokumenty: odkazy na `ulovklienty.cz/dokumentace.html` (jedna entita — Jiří Hakl).
- E-maily: `info@modernik.cz`, `hakl@modernik.cz` (DNS/přesměrování nastavit před LIVE).

## Větev

Příprava rebrandu: `feature/modernik-rebrand`
