# Partner onboarding runbook (agent)

Canonical procedure to take **any** new partner from zero to custom-domain LIVE.  
Human-readable twin: [`dokumenty/NASTAVENI_NOVEHO_PARTNERA.md`](../dokumenty/NASTAVENI_NOVEHO_PARTNERA.md).

**Out of scope for this runbook:** vertical branding/layout, shared bugfixes across all demos, marketing copy.

## Placeholders

| Token | Meaning |
|-------|---------|
| `<SLUG>` | Folder name under repo root / `www/` (e.g. `provoz-foo`) |
| `<SALON_ID>` | Integer PK — **same** in DB, `app.js` / `web-admin.js` / `rezervace.js` |
| `<OWNER_EMAIL>` | Unique owner login (must not exist on other salons) |
| `<DOMAIN>` | Apex host (e.g. `partner.example`) |
| `<SMTP_USER>` | Mailbox used for From / IMAP (often `info@<DOMAIN>`) |
| `<SERVER_IP>` | LIVE Hetzner A target (currently `49.13.23.65`) |

## Iron rules

```
LOCAL → GitHub DEV → staging → (approval) → MAIN → LIVE → domain/SSL
```

- LIVE deploy only after explicit user OK; use `deploy/deploy-live.sh` (backup, `pre-deploy-check`, **no** `--delete` by default).
- Never sync an incomplete partner folder (needs at least `index.html`).
- Touch **only** `<SLUG>/`, shared wiring if required, nginx partner vhost, and salon `<SALON_ID>` DB rows — do not rewrite other partners’ sites.
- Staging mail → `EMAIL_OVERRIDE_TO`; LIVE mail → partner SMTP.

## Phase A — Staging DB partner

1. Staging partner-admin: create partner (name, contacts, `<OWNER_EMAIL>`, password, activate FLOW).
2. Record `<SALON_ID>` returned / shown.
3. Ensure `RezervacniNastaveni` exists (create path usually does).

## Phase B — Static site (git)

1. New isolated directory `<SLUG>/` (copy structure from a complete similar demo if needed, then set IDs).
2. Hardcode `SALON_ID = <SALON_ID>` in site JS.
3. Wire owner FLOW per [`shared/OWNER_FLOW_WIRING.md`](../shared/OWNER_FLOW_WIRING.md) (`owner-flow-admin.js` + `UlovOwnerFlowConfig` + `onAdminShown`).
4. API base pattern: localhost → `:8000`, staging host → `api-staging…`, else `api.ulovklienty.cz`.
5. `bash deploy/pre-deploy-check.sh <SLUG>` before any deploy.
6. Commit + push **DEV** only.

Optional map entry (fallback when DB URL empty):

- [`backend/rezervace/services/booking_urls.py`](../backend/rezervace/services/booking_urls.py) `DEMO_LIVE_BOOKING_URLS[<SALON_ID>]`
- Staging rewrite of Ulov hosts is already in `resolve_rezervace_web_url` when `SENTRY_ENVIRONMENT` / API URL indicates staging.

## Phase C — Staging deploy + configure

```bash
# on server
cd /opt/ulov && bash deploy/deploy-staging.sh origin/dev
```

Configure salon `<SALON_ID>` (admin UI or shell):

| Field | Staging value |
|-------|----------------|
| `web_rezervace_url` | `https://www.staging.ulovklienty.cz/<SLUG>/rezervace.html` |
| SMTP | provider host/port; **587 + STARTTLS** if Forpsi from Hetzner (not 465 SSL) |
| `smtp_user` / password | `<SMTP_USER>` + mailbox password |
| `email_odesilatel` / display name | align with mailbox |
| IMAP | optional; `imap_enabled=true`, same login as SMTP |

Smoke: site, booking → confirm mail CTA, owner login → FLOW.

`get_email_config`: if SMTP password missing → falls back to global Ulov SMTP (wrong From). Always set partner password on LIVE.

## Phase D — LIVE

1. User approves → merge DEV → MAIN → `bash deploy/deploy-live.sh origin/main`.
2. If LIVE DB lacks `<SALON_ID>`: create **only** that salon with **forced pk=`<SALON_ID>`** (frontend is hardcoded). Next free id must be available (`MAX(id) < <SALON_ID>` or exact gap).
3. Owner email uniqueness: `Zamestnanec.prihlasovaci_jmeno` / `FlowUser.email` unique — pick another email if conflict.
4. Copy SMTP/IMAP from staging (password included) or re-enter via partner-admin; set:

```text
web_rezervace_url = https://www.ulovklienty.cz/<SLUG>/rezervace.html
```

(until custom domain)

5. Smoke LIVE Ulov path + API health; other partners must stay 200.

Tag LIVE deploy for rollback when practical.

## Phase E — Custom domain + SSL

### E1 — DNS (human at registrar)

Edit **only** apex **A** → `<SERVER_IP>`.  
Keep MX / SPF / DKIM / DMARC / autoconfig.  
If `*.<DOMAIN>` CNAME → apex, do **not** add a separate `www` A unless required.

Verify authoritative NS:

```bash
dig +short <DOMAIN> A @<registrar-ns>
# expect <SERVER_IP>
```

### E2 — Nginx vhost

Add `deploy/nginx/conf.d/partner-<slug>.conf`:

- `:80` — `server_name <DOMAIN> www.<DOMAIN>`; ACME `root /var/www/certbot`; redirect else to HTTPS
- `:443` — `root /var/www/sites/<SLUG>`; `location /shared/` → `alias /var/www/sites/shared/`
- cert paths under `/etc/letsencrypt/live/<DOMAIN>/`

Do **not** edit other partners’ vhosts or use `rsync --delete` on `www/`.

Template pattern: [`deploy/nginx/conf.d/partner-franek.conf`](nginx/conf.d/partner-franek.conf) + [`deploy/issue-partner-franek-cert.sh`](issue-partner-franek-cert.sh) (generalize name/domain for next partner).

### E3 — Certificate

HTTP-only vhost first (so `nginx -t` does not require missing certs) → `certbot certonly --webroot` for `<DOMAIN>` and `www.<DOMAIN>` → enable full HTTPS conf → `nginx -s reload`.

### E4 — CORS + booking URL

Append to LIVE `.env` (then recreate `api`):

```text
CORS_ALLOWED_ORIGINS=…,https://<DOMAIN>,https://www.<DOMAIN>
CSRF_TRUSTED_ORIGINS=…,https://<DOMAIN>,https://www.<DOMAIN>
```

```text
web_rezervace_url = https://www.<DOMAIN>/rezervace.html
```

Optionally set `PartnerNastaveni.domena = <DOMAIN>`.

Update `DEMO_LIVE_BOOKING_URLS[<SALON_ID>]` in git to the custom URL as fallback.

### E5 — Smoke

```bash
curl -I https://<DOMAIN>/
curl -I https://www.<DOMAIN>/rezervace.html
curl -I https://www.<DOMAIN>/shared/creator-footer.css
# also: previous Ulov path + one unrelated demo + api /health/
```

Confirm TLS: `openssl s_client -servername www.<DOMAIN> -connect www.<DOMAIN>:443`.

## Isolation checklist (every change)

- [ ] Only `<SLUG>/` static + partner nginx file + salon `<SALON_ID>` settings
- [ ] No `--delete` rsync to LIVE `www/`
- [ ] No incomplete folder deploy
- [ ] Owner email unique on target environment
- [ ] `web_rezervace_url` never left as `localhost` on staging/LIVE
- [ ] SMTP password set before declaring mail “done”

## Related

- [`DEPLOY_PIPELINE.md`](DEPLOY_PIPELINE.md)
- [`DEPLOY_SAFETY.md`](DEPLOY_SAFETY.md)
- [`../shared/OWNER_FLOW_WIRING.md`](../shared/OWNER_FLOW_WIRING.md)
- [`.cursor/rules/deploy-safety.mdc`](../.cursor/rules/deploy-safety.mdc)
