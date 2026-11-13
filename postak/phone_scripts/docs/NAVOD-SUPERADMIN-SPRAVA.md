# Telefonní klikačka – návod pro superadmina (LOCAL)

## Přístup

- **Klikačka:** `/telefonni-klikacka/`
- **Správa scénářů:** `/telefonni-klikacka/sprava/` (pouze superuser)

## Typický postup

1. Připravte JSON podle `OBSAH-SCENARE-JSON.md`.
2. **Správa scénářů → Import JSON** (nebo nový scénář → import).
3. Po úspěchu je verze ve stavu **Koncept** – telefonisty se to nedotkne.
4. **Testovat** na detailu verze (otevře klikačku s danou verzí).
5. **Publikovat** po potvrzení – stará publikovaná verze přejde do **Archiv**.
6. **Export** kdykoli pro zálohu.

## Návrat na starší verzi

1. Otevřete **Verze** u scénáře.
2. U archivní verze zvolte **Publikovat** (bez opětovného uploadu JSON).

## Deaktivace

Na seznamu scénářů **Deaktivovat** – scénář zmizí běžným uživatelům z výběru (superadmin ho stále vidí).

## Formát JSON

Beze změny vůči fázi 1 (`demo-modernik.export.json`).

## Omezení

- Běžný uživatel vidí jen **aktuální publikovanou** verzi aktivního scénáře.
- Import je atomický – při chybě se data neuloží.
- `dry-run` u management command na CLI nekontroluje celý graf (webová validace při importu ano).
