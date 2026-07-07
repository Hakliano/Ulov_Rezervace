# Salony – lokální projekt (Django API + statický frontend)

Dva nezávislé weby salonů (`salon1`, `salon2`) sdílejí jeden Django backend s REST API, SQLite databází a úložištěm obrázků na [Bunny.net](https://bunny.net).

## Struktura

```
backend/          Django + DRF API (localhost:8000)
salon1/           Frontend salonu ID 1 (Salon Elegance)
salon2/           Frontend salonu ID 2 (Studio Krása)
salon3/           Frontend salonu ID 3 (CRAZY — neon / hype styl)
salon4/           Frontend salonu ID 4 (U dvou přátel — francouzská kavárna)
presentace/       Prezentační web prodeje systému (bez rezervací, formulář poptávky)
```

## Spuštění backendu

```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_salons
python manage.py seed_rezervace
python manage.py runserver
```

API běží na **http://localhost:8000**

### API endpointy

| Metoda | URL | Popis |
|--------|-----|-------|
| GET | `/api/salon/1/` | Data salonu včetně obrázků |
| GET | `/api/salon/2/` | Data salonu 2 |
| PUT | `/api/salon/<id>/` | Úprava textů (hlavička `X-Admin-Password`) |
| POST | `/api/salon/<id>/upload/` | Nahrání obrázku (multipart, pole `file`, `typ`: `hero` nebo `galerie`) |
| DELETE | `/api/salon/<id>/obrazek/<image_id>/` | Smazání obrázku z galerie |
| GET | `/api/bunny/status/` | Zda je Bunny.net nakonfigurován |
| POST | `/api/auth/login/` | Ověření hesla `{"password": "admin123"}` |
| POST | `/api/poptavka/` | Poptávka z prezentačního webu (jméno, e-mail, souhlas) |

### Rezervační API (Ulov Rezervaci)

| Metoda | URL | Popis |
|--------|-----|-------|
| GET | `/api/salon/<id>/rezervace/info/` | Služby, zaměstnanci, nastavení |
| GET | `/api/salon/<id>/rezervace/volne-terminy/?datum=&sluzby=1,2&zamestnanec=` | Volné sloty |
| POST | `/api/salon/<id>/rezervace/` | Vytvoření rezervace (veřejné) |
| POST | `/api/salon/<id>/rezervace/storno/<token>/` | Storno bez přihlášení |
| GET | `/api/salon/<id>/rezervace/<id>/ics/` | Kalendářový soubor |
| POST | `/api/salon/<id>/rezervace/zakaznik/registrace/` | Registrace (nick + e-mail + GDPR) |
| POST | `/api/salon/<id>/rezervace/zakaznik/prihlaseni/` | Přihlášení tokenem e-mailem |
| GET | `/api/salon/<id>/rezervace/zakaznik/moje/?token=` | Moje rezervace |
| GET/PUT | `/api/salon/<id>/rezervace/admin/...` | Správa personálu (hlavička `X-Admin-Password`) |

Životní cyklus rezervací (e-maily, anonymizace): `python manage.py rezervace_zivotni_cyklus` (cron, hodinově). Viz [ZIVOTNI_CYKLUS_REZERVACE.md](ZIVOTNI_CYKLUS_REZERVACE.md).

## Bunny.net – nastavení obrázků

Obrázky se ukládají do vaší Storage Zone na Bunny.net a servírují přes CDN.

### 1. Zkopírujte konfiguraci

```bash
cd backend
copy .env.example .env
```

### 2. Vyplňte hodnoty z [Bunny Dashboard](https://dash.bunny.net/storage)

Ve vaší Storage Zone (složka `webs`):

| Proměnná | Kde najít |
|----------|-----------|
| `BUNNY_STORAGE_ZONE` | FTP & HTTP API → **Username** (název zóny) |
| `BUNNY_STORAGE_API_KEY` | FTP & HTTP API → **Password** |
| `BUNNY_CDN_BASE_URL` | Linked Pull Zone → hostname, např. `https://vase-zona.b-cdn.net` |
| `BUNNY_STORAGE_PATH_PREFIX` | `webs` (vaše existující složka) |
| `BUNNY_STORAGE_REGION` | Volitelné – např. `de`, `ny` (prázdné = výchozí) |

Soubory se ukládají do: `webs/salon-1/hero/…` a `webs/salon-1/galerie/…`

Při nahrání backend **automaticky zmenší** obrázek (delší strana max **1920 px**) a zkomprimuje (JPEG/WebP kvalita 85). Nastavení v `.env`: `IMAGE_UPLOAD_MAX_PX`, `IMAGE_UPLOAD_JPEG_QUALITY`, `IMAGE_UPLOAD_WEBP_QUALITY`. Animované GIFy se nemění.

### 3. Restartujte backend

Po uložení `.env` restartujte `runserver`.

### 4. Nahrávání v administraci

1. Otevřete web salonu → **Administrace** → heslo `admin123`
2. Záložka **Obrázky**
3. **Nahrát hero fotku** – velký banner nahoře na webu
4. **+ Přidat do galerie** – fotky do sekce Galerie

## Spuštění frontendu

Doporučeno přes lokální server (kvůli CORS a `fetch`):

```bash
cd salon1
python -m http.server 5500
```

- Salon 1: **http://localhost:5500** · Rezervace: **http://localhost:5500/rezervace.html**
- Salon 2: port `5501` · Rezervace: **http://localhost:5501/rezervace.html**
- Salon 3 (CRAZY): port `5502` · Rezervace: **http://localhost:5502/rezervace.html**

Salon CRAZY přidáte do DB: `python manage.py seed_salon_crazy` (jen pokud ještě neexistuje).
Salon U dvou přátel: `python manage.py seed_salon_dva_pratele` · port **5503**

### Prezentační web (prodej systému)

**Doporučeno — jeden server pro celý projekt** (odkazy na dema fungují spolehlivě):

```bash
cd weby_s_externi_DTB
python -m http.server 8080
```

- Prezentace: **http://localhost:8080/presentace/**
- Salon 1: **http://localhost:8080/salon1/** · Salon 2: **/salon2/** · atd.

Alternativně prezentace zvlášť na portu 5510 — odkazy na dema pak míří na porty 5500–5503 (salony musí běžet):

```bash
cd presentace
python -m http.server 5510
```

- **http://localhost:5510** — landing s odkazy na demo salony 1–4 a formulářem poptávky (bez rezervací)
- API: `POST /api/poptavka/` — odešle e-mail přes SMTP salonu 2 (Studio Krása)
- Volitelně v `.env`: `POPTAVKA_EMAIL=vas@email.cz` (jinak e-mail salonu 2)

### Sdílené SMTP pro testování (salony 3 a 4)

Po nastavení SMTP u salonu 2 (⚙ → E-mail nebo `backend/.env`):

```bash
python manage.py sync_smtp_salon2
```

Zkopíruje SMTP host, port, uživatele a heslo ze salonu 2 do salonů 3 (CRAZY) a 4 (U dvou přátel), aby šly testovat potvrzovací e-maily.

Na hlavní stránce každého salonu je tlačítko **Rezervovat termín** → samostatná rezervační stránka propojená s DB.

### Rezervační frontend

Každý salon má vlastní `rezervace.html` ve stejném designu jako hlavní web:

1. **Nová rezervace** – výběr služeb (více najednou), termínu, pracovníka („Je mi to jedno“), GDPR údaje
2. **Moje rezervace** – registrace/přihlášení (nick + e-mail), historie, storno
3. **Personál** – kalendář, statistiky, nastavení (heslo `admin123`)

E-maily (potvrzení, storno, připomínka, poděkování) se v dev režimu vypisují do konzole backendu.

## Administrace

1. Tlačítko **⚙** vpravo dole
2. Heslo: **`admin123`**
3. Záložky: Základní · Obrázky · Ceník · Novinky · Otevírací doba
4. **Uložit textová data** – uloží texty (obrázky se nahrávají samostatně tlačítky)

Heslo lze změnit v `backend/salon_api/settings.py` (`SALON_ADMIN_PASSWORD`).
