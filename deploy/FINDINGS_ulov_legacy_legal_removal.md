# Odstranění zastaralé právní dokumentace ULOV KLIENTY

| Položka | Hodnota |
|--------|---------|
| Datum | 28. 10. 2026 |
| Commit (dev) | `fc5a82c` |
| Prostředí | **STAGING** (LIVE až po schválení) |
| Archivní kopie | `archive/ulov-legal-legacy-20261028/` (mimo `presentace/`, nenasazuje se) |

## Odstraněné veřejné URL (očekávaný HTTP 410)

| URL | Soubor |
|-----|--------|
| `/dokumentace.html` | `presentace/dokumentace.html` |
| `/vop.html` | `presentace/vop.html` |
| `/gdpr.html` | `presentace/gdpr.html` |
| `/dpa.html` | `presentace/dpa.html` |
| `/smlouva.html` | `presentace/smlouva.html` |
| `/specifikace.html` | `presentace/specifikace.html` |
| `/subzpracovatele.html` | `presentace/subzpracovatele.html` |

## Odstraněné z veřejného deploye (nebyly samostatné „dokumenty“, ale publikované)

| Soubor | Důvod |
|--------|--------|
| `presentace/vop.css` | Styl jen pro odstraněné dokumenty |
| `presentace/index.hub-legacy.html` | Záloha starého hubu s odkazy na staré dokumenty |
| `presentace/index.marketing-ulov-backup.html` | Marketingová záloha s odkazy na staré dokumenty |

## Zachováno / přidáno

| URL | Účel |
|-----|------|
| `/pravni-dokumenty/` | Jediný rozcestník (Moderník + HereYouAre) |
| `/cookies.html` | **Nové** aktuální cookies zásady hubu (GA vypnuté) |
| Navigace „Právní dokumenty“ | Beze změny |

## Sitemap

V repozitáři nebyl nalezen `sitemap.xml` pro hub. Nic k mazání.

## Nginx

`return 410` pro výše uvedené cesty v:

- `deploy/nginx/conf.d/staging.conf` (nasazeno se STAGING)
- `deploy/nginx/conf.d/webs.conf` (LIVE až po schválení + reload nginx)

## Poznámka k evidenci

Archiv v `archive/ulov-legal-legacy-20261028/` + historie gitu — pro historické smluvní vztahy / interní evidenci, **ne veřejný web**.
