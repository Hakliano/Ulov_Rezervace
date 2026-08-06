# Testovací přístupy (demo majitelé)

Interní cheat sheet pro přihlášení majitele na web (⚙) a do FLOW.  
Aktualizace: **2026-08-05** (po nasazení Karty zákazníka na LIVE, SHA `612475e`).

## Společné

| | LIVE | Staging |
|--|------|---------|
| Heslo majitele (demo default) | `majitelka123` | stejně (pokud nebyl seed/obnova jinak) |
| FLOW | https://www.ulovklienty.cz/flow/ | https://www.staging.ulovklienty.cz/flow/ |
| Hub | https://www.ulovklienty.cz/ | https://www.staging.ulovklienty.cz/ |
| API | https://api.ulovklienty.cz/ | https://api-staging.ulovklienty.cz/ |
| Partner-admin (superadmin) | https://api.ulovklienty.cz/partner-admin/ | https://api-staging.ulovklienty.cz/partner-admin/ |

**Login = e-mail** (už ne username `majitelka`). Stejný e-mail + heslo funguje na webu i ve FLOW.

Partner-admin vyžaduje **Django superuser**, ne login majitelky salonu.  
Hub `ulovklienty.cz/partner-admin/` přesměruje na API.

Starý sdílený login `majitelka` / `majitelka` je zrušený — každý salon má unikátní e-mail.

Obsahová administrace webu (hlavička `X-Admin-Password`, lokálně): `admin123` — to **není** heslo majitele do FLOW.

Potvrzovací odkazy zákaznické karty: LIVE → `https://api.ulovklienty.cz/api/...`, staging → `https://api-staging.ulovklienty.cz/api/...`.

---

## Beauty dema (salon 1–8)

| ID | Demo | Login majitele | LIVE web | Staging web |
|----|------|----------------|----------|-------------|
| 1 | Salon Elegance | `info@ulovklienty.cz` | https://demo1.ulovklienty.cz/ | https://www.staging.ulovklienty.cz/salon1/ |
| 2 | Studio Krása | `majitel.salon2@ulov.local` | https://demo2.ulovklienty.cz/ | https://www.staging.ulovklienty.cz/salon2/ |
| 3 | CRAZY | `majitel.salon3@ulov.local` | https://demo3.ulovklienty.cz/ | https://www.staging.ulovklienty.cz/salon3/ |
| 4 | U dvou přátel | `majitel.salon4@ulov.local` | https://demo4.ulovklienty.cz/ | https://www.staging.ulovklienty.cz/salon4/ |
| 5 | Wellness Gold | `majitel.salon5@ulov.local` | https://demo5.ulovklienty.cz/ | https://www.staging.ulovklienty.cz/salon5/ |
| 6 | Salon Klid | `majitel.salon6@ulov.local` | https://demo6.ulovklienty.cz/ | https://www.staging.ulovklienty.cz/salon6/ |
| 7 | Silver kosmetika | `majitel.salon7@ulov.local` | https://demo7.ulovklienty.cz/ | https://www.staging.ulovklienty.cz/salon7/ |
| 8 | RELAX | `majitel.salon8@ulov.local` | https://demo8.ulovklienty.cz/ | https://www.staging.ulovklienty.cz/salon8/ |

Cesta `/salonN/` na LIVE www vrací 404 (nginx mapuje jen `demoN` hosty).

**Ověřeno 2026-08-05 LIVE FLOW:** CRAZY `majitel.salon3@ulov.local` / `majitelka123` OK (včetně API Zákaznické karty).  
`info@ulovklienty.cz` na LIVE teď **nebere** `majitelka123` (heslo pravděpodobně změněno) — reset přes partner-admin / FLOW aktivaci.  
RentGo (`info@rentgo.cz` / `majitelka123`) OK.

---

## Vertikální dema (salon 9–17)

| ID | Demo | Složka | Login majitele | LIVE web |
|----|------|--------|----------------|----------|
| 9 | Movium (fyzio) | `zdravi-fyzio/` | `info@movium.cz` | https://www.ulovklienty.cz/zdravi-fyzio/ |
| 10 | PawCare (veterina) | `zdravi-veterina/` | `info@pawcare.cz` | https://www.ulovklienty.cz/zdravi-veterina/ |
| 11 | Bělice (dental) | `zdravi-dental/` | `info@belice.cz` | https://www.ulovklienty.cz/zdravi-dental/ |
| 12 | VodaPro (instalatér) | `remesla-instalater/` | `info@vodapro.cz` | https://www.ulovklienty.cz/remesla-instalater/ |
| 13 | VOLT (elektrikář) | `remesla-elektrikar/` | `info@volt.cz` | https://www.ulovklienty.cz/remesla-elektrikar/ |
| 14 | Ateliér Domov | `remesla-rekonstrukce/` | `majitel.salon14@ulov.local` | https://www.ulovklienty.cz/remesla-rekonstrukce/ |
| 15 | MotorBay | `provoz-autoservis/` | `info@motorbay.cz` | https://www.ulovklienty.cz/provoz-autoservis/ |
| 16 | RentGo | `provoz-pujcovna/` | `info@rentgo.cz` | https://www.ulovklienty.cz/provoz-pujcovna/ |
| 17 | Ateliér 42 | `provoz-studio/` | `majitel.salon17@ulov.local` | https://www.ulovklienty.cz/provoz-studio/ |

Staging: stejná cesta pod `https://www.staging.ulovklienty.cz/…` (např. `/zdravi-fyzio/`).

---

## Jak se přihlásit

1. Otevři demo web → ⚙ (personál / majitel).
2. E-mail + `majitelka123` (pokud heslo nebylo změněno).
3. **Přejít do FLOW** (nebo přímo FLOW URL) — stejný e-mail + heslo.
4. Rezervace: `…/rezervace.html` (bez admin záložek personálu — denní provoz je ve FLOW).
5. Karta zákazníka: FLOW → záložka **Zákazníci**.

---

## Ověření / obnova loginů v DB

```bash
# na serveru (LIVE nebo staging compose)
docker compose exec -T api python manage.py ensure_unique_owner_emails --dry-run
docker compose exec -T api python manage.py ensure_unique_owner_emails
```

Seed vertikál nastaví default `majitel.salon{N}@ulov.local` + heslo `majitelka123`.  
Na LIVE mohou zůstat brandové e-maily ze `Salon.email` (viz tabulky výše).

Po změně hesla majitelem v záložce **Heslo** už `majitelka123` neplatí — reset přes partner-admin nebo FLOW aktivaci.

Pro FLOW musí existovat i `FlowUser` (nejen `Zamestnanec`) se stejným e-mailem.

---

## Poznámky

- Dokument je interní; hesla dem nejsou pro ostré partnery.
- Staging DB je kopie / seed — loginy se mohou lišit od LIVE; při pochybnosti dry-run výše.
- Wiring FLOW na webu: [`shared/OWNER_FLOW_WIRING.md`](../shared/OWNER_FLOW_WIRING.md).
