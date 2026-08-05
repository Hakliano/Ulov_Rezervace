# FLOW – Karta zákazníka (`feature/flow-customer-card`)

**Jen lokál / feature branch.** Na LIVE nenasazovat, dokud není schváleno.

## Odříznutí / rollback

```bash
# zahodit větev (pokud není merge)
git checkout dev
git branch -D feature/flow-customer-card

# pokud už bylo merge do dev — revert commitů s touto feature
```

Soubory feature (lze smazat ručně):

| Cesta | Účel |
|-------|------|
| `backend/flow/customer_card_*.py` | model, API, e-mail, služby |
| `backend/flow/migrations/0003_customer_card.py` | DB |
| `backend/flow/templates/flow/customer_card_*` + `emails/customer_card_*` | potvrzení |
| `flow/customer-card.js` | UI |
| úpravy v `flow/urls.py`, `provoz_views.py`, `models.py` import, `tasks.py`, `flow/index.html`, `style.css` | napojení |

DB: `python manage.py migrate flow zero` **NE** — raději `migrate flow 0002` po odstranění 0003, pokud migrace běžela jen lokálně.

## Lokální test bez e-mailu

Na localhostu u karty ve stavu „čeká“ je tlačítko **Aktivovat lokálně (bez e-mailu)**  
(`POST /api/flow/zakaznicke-karty/<id>/aktivovat-lokalne/` — jen `DEBUG=True`).

E-mailové potvrzení testovat až na stagingu.

## Nová rezervace ze karty

U **aktivní** karty tlačítko **Nová rezervace** otevře stávající `#form-nova` (`openNova`) a předvyplní jméno + e-mail.  
Do interní poznámky: telefon (pokud je) + popis zákazníka z karty (`poznamka`).  
Uložení = stávající `POST /api/flow/rezervace/`. Vazba karta↔rezervace = runtime shoda e-mailu u aktivní karty (bez FK).

## Architektura

- Tabulky `flow_customercard`, `flow_customervisit` — **bez FK** na `rezervace_rezervace`.
- Tenant = `salon_id` (Partner v produktu).
- Unique `(salon, email)`.
- Odkaz z rezervace: runtime enrichment `customer_card_id` jen u **aktivních** karet.

## API

| Method | Path | Auth |
|--------|------|------|
| GET/POST | `/api/flow/zakaznicke-karty/` | X-Flow-Token |
| GET | `/api/flow/zakaznicke-karty/lookup/?email=` | X-Flow-Token |
| GET/PATCH/DELETE | `/api/flow/zakaznicke-karty/<id>/` | X-Flow-Token |
| POST | `/api/flow/zakaznicke-karty/<id>/odeslat-potvrzeni/` | X-Flow-Token |
| POST | `/api/flow/zakaznicke-karty/<id>/navstevy/` | X-Flow-Token |
| GET/POST | `/api/flow/zakaznicka-karta/potvrdit/<token>/` | veřejné |

## Lokální test

```bash
cd backend
python manage.py migrate flow
python manage.py runserver
# FLOW: http://localhost…/flow/ → záložka Zákazníci
```

Volitelně: `CUSTOMER_CARD_CONFIRM_BASE_URL=http://localhost:8000/api`
