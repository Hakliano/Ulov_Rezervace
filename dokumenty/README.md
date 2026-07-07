# Dokumenty pro compliance a partnery

Právní a compliance dokumentace platformy **Ulov Rezervaci** ve formátu vhodném pro tisk a odeslání partnerům (salony).

## Sales a marketing

| Dokument | Zdroj (MD) | HTML | PDF |
|----------|------------|------|-----|
| Přehled pro sales a marketing | `../PREHLED_PRO_SALES_A_MARKETING.md` | `prehled-pro-sales-a-marketing.html` | `pdf/PREHLED-pro-sales-a-marketing.pdf` |

```powershell
cd dokumenty
python generate_sales_pdf.py
```

Po úpravě `.md` v kořeni projektu spusťte znovu — HTML i PDF se přegenerují automaticky.

## Soubory

| Dokument | HTML (náhled / tisk) | PDF |
|----------|----------------------|-----|
| Smlouva o zpracování osobních údajů (DPA) | `smlouva-o-zpracovani-osobnich-udaju.html` | `pdf/Smlouva-o-zpracovani-osobnich-udaju.pdf` |
| Příloha č. 1 — Kategorie údajů | `priloha-01-kategorie-osobnich-udaju.html` | `pdf/Priloha-01-kategorie-osobnich-udaju.pdf` |
| Příloha č. 2 — Technická a organizační opatření | `priloha-02-technicka-organizacni-opatreni.html` | `pdf/Priloha-02-technicka-organizacni-opatreni.pdf` |
| Příloha č. 3 — Další zpracovatelé (subdodavatelé) | `priloha-03-dalsi-zpracovatele.html` | `pdf/Priloha-03-dalsi-zpracovatele.pdf` |

## Interní compliance dokumenty

| Dokument | HTML | PDF |
|----------|------|-----|
| ROPA — Záznamy o činnostech zpracování (čl. 30 GDPR) | `ropa-zaznamy-o-cinnostech-zpracovani.html` | `pdf/ROPA-zaznamy-o-cinnostech-zpracovani.pdf` |

## Jak získat PDF

### Automaticky (Windows + Microsoft Edge)

```powershell
cd dokumenty
python generate_pdf.py
```

### Ručně v prohlížeči

1. Otevřete příslušný soubor `.html` v Chrome nebo Edge.
2. Klikněte na **„Uložit jako PDF / Tisk“** (nebo Ctrl+P).
3. Cíl tisku: **Uložit jako PDF**.

## Poznámka

Soubory `.md` v kořeni projektu slouží jako pracovní / technická verze. Pro partnery a compliance používejte **HTML a PDF** z této složky.
