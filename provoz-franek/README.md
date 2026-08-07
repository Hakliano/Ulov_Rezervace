# provoz-franek (Fraňek Autoservis)

Izolovaný web partnera — **salon ID 18** (staging).

## Co je napojené

- Veřejné sekce: Galerie, Personál, Ceník, Novinky, Otevírací doba, kontaktní údaje — data z API / web-adminu
- Web-admin (⚙) + owner FLOW přes `../shared/owner-flow-admin.js` (read-only import)
- Creator patička Ulov (`../shared/creator-footer.css`)
- Vlastní UI: nav silnice, hero scan/odjezd — `app.js`

## API

- Staging host → `https://api-staging.ulovklienty.cz/api`
- LIVE host → `https://api.ulovklienty.cz/api`
- `SALON_ID = 18` jen v `web-admin.js` tohoto folderu

## Bezpečnost

- Neměnit jiné `salon*` / `provoz-*` dema ani shared zdroje (jen číst)
- Prázdné sekce se skryjí, dokud v adminu nejsou data

## URL

https://www.staging.ulovklienty.cz/provoz-franek/
