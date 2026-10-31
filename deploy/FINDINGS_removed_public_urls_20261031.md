# Zrušení vybraných veřejných URL (2026-10-31)

| Položka | Hodnota |
|--------|---------|
| Archiv | `archive/removed-public-urls-20261031/` (mimo webroot) |
| Oprava | `dekujeme.html` — čitelný tmavý text na bílém poli (modernik + hub) |

## Zrušeno (očekávaný HTTP 410)

| URL | Nginx |
|-----|--------|
| `https://www.modernik.cz/spocitat-cenu/` | `modernik.conf` |
| `https://www.modernik.cz/co-pracuje-v-pozadi.html` | `modernik.conf` |
| `https://www.ulovklienty.cz/beauty/` | `webs.conf` (+ staging) |
| `https://www.ulovklienty.cz/zdravi/` | `webs.conf` (+ staging) — **ne** `/zdravi-fyzio/` atd. |
| `https://www.ulovklienty.cz/remesla/` | `webs.conf` (+ staging) — **ne** `/remesla-instalater/` atd. |
| `https://www.ulovklienty.cz/provozovny/` | `webs.conf` (+ staging) |

## Nezrušeno (ops)

`https://api.ulovklienty.cz/health/` zůstává — monitorování / deploy smoke. Vypnout jen na výslovné potvrzení.
