# Nasazení Telefonní klikačky (STAGING / LIVE)

## Co Git přenáší

- Kód aplikace `phone_scripts`, migrace schématu, šablony, JS/CSS, testy, dokumentaci.
- Technická šablona: `fixtures/schema-empty.template.json`

## Co Git nepřenáší

- Žádná data scénářů z databáze.
- Demo/export JSON (ignorováno v `fixtures/.gitignore`).
- Příkazy `seed_phone_script_demo` / `generate_phone_script_stress` se při nasazení **nespouštějí**.

## STAGING

```bash
# Na serveru (Hetzner), v kořeni monorepa:
bash deploy/postak/deploy-staging-postak.sh origin/dev
```

Ověření URL: https://www.staging.ulovklienty.cz/postak/telefonni-klikacka/

Migrace: součást deploy skriptu (`migrate --noinput`).

Prázdný stav scénářů je očekávaný — první JSON nahraje superadmin v `/telefonni-klikacka/sprava/`.

## LIVE

Pouze po schválení STAGING. Před nasazením záloha DB. Stejný postup jako STAGING s `docker-compose.live.yml` a `.env.live`.

## Chyba vstupní větve (oprava)

Atribut `data-style` na tlačítkách stylu prodeje kolidoval s DOM `element.style`.
Používáme `data-sales-style` a čtení přes `getAttribute`.

## Oslovení „Vaše Jméno“ (B. otevřené)

Zatím neimplementováno — lze řešit v JSON (`{agent_name}` nebo statický text s HTML kurzívou po schválení).
