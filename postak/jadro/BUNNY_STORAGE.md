# Bunny.net Storage — Pošťák

## Účel

Centrální úložiště pro **fotografie, letáky, loga, PDF a marketingové materiály** týmu, plus profilové fotografie a přílohy e-mailových konceptů v Pošťáku.

Storage Zone: **`wwweb`** (Frankfurt)  
Prefix: **`postak/`** — `https://storage.bunnycdn.com/wwweb/postak/...`

| Prostředí | Doporučený prefix |
|-----------|-------------------|
| LOCAL / test | `postak/local/` |
| STAGING | `postak/staging/` |
| LIVE (až po schválení) | `postak/` |

Žádné speciální šifrování ani složitá infrastruktura nad rámec Bunny Storage + Django.

## Sdílené vs. moje (PUBLIC / PRIVATE v aplikaci)

- **Sdílené dokumenty** — materiály pro celý tým (marketing, loga, letáky). V aplikaci je vidí všichni přihlášení; zápis má SUPERUSER. Nejde o „utajení souboru na internetu“.
- **Moje dokumenty** — osobní pracovní soubory uživatele; ostatní je nevidí, SUPERUSER může spravovat.

Veřejné **CDN odkazy** na běžné marketingové soubory ve sdílené dokumentaci jsou v pořádku (Pull Zone mimo Pošťák). Aplikace **nezakládá** veřejné URL z `FileField` — stahování a nahrávání jde přes Pošťák s kontrolou oprávnění; přímý CDN link lze doplnit v Bunny/Pull Zone podle potřeby.

## Přístupové údaje (pouze server)

V `.env`, nikdy v gitu, frontendu ani v databázi:

- `POSTAK_BUNNY_ENABLED=true`
- `POSTAK_BUNNY_STORAGE_ZONE=wwweb`
- `POSTAK_BUNNY_ACCESS_KEY=` — heslo Storage Zone
- `POSTAK_BUNNY_API_BASE=https://storage.bunnycdn.com` (volitelné)
- `POSTAK_BUNNY_ROOT_PREFIX=postak/local` nebo `postak`

Klient odmítá cesty mimo `POSTAK_BUNNY_ROOT_PREFIX` (aplikace nepíše mimo `postak/`).

## Technické chování

- **Default storage:** `jadro.postak_storage.PostakBunnyStorage` — při vypnutém Bunny lokální `MEDIA_ROOT`.
- **Stahování v aplikaci:** `dokumentace_stahnout`, `profil_foto` atd. — přihlášení + oprávnění (beze změny, pokud vyhovuje).
- **Nahrání / mazání / přesun:** jen podle rolí v Pošťáku (sdílené = SUPERUSER, moje = vlastník).

## Záloha a inventura

1. `python manage.py postak_bunny_inventory` — cesty z DB  
2. `python manage.py postak_bunny_inventory --remote` — výpis na Bunny (volitelné)  
3. `python manage.py postak_bunny_backup <archive.zip>` — ZIP + `manifest.json`  
4. `python manage.py postak_bunny_smoke` — integrační test PUT/GET/DELETE (LOCAL)

## LOCAL

Bez `POSTAK_BUNNY_ENABLED` zůstává vše na disku (testy). Integrační testy Bunny používejte s prefixem **`postak/local`**.
