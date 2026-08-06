# MacBook setup — instrukce pro Cursor Agent

> **Jak použít:** Na MacBooku otevři tento soubor v Cursoru (Agent mode) a napiš:
> `Proveď setup podle deploy/MACBOOK_CURSOR_SETUP.md`
>
> Pokud repo ještě není naklonované, zkopíruj **jen tento soubor** na Mac (AirDrop / USB / e-mail), otevři ho v Cursoru a řekni totéž. Agent nejdřív nainstaluje nástroje, pak naklonuje repo.

---

## Role agenta

Jsi setup agent. Cíl: připravit tento MacBook na vývoj Ulov (GitHub + větve `dev`/`main` + SSH deploy na Hetzner).

- Prováděj kroky **postupně**, ověřuj výsledek každého kroku.
- Kde je potřeba lidská akce (GitHub UI, vložení klíče na server), **zastav a řekni uživateli přesně co udělat**.
- Nikdy necommituj secrety (`.env`, privátní klíče).
- Nikdy nespouštěj LIVE deploy bez výslovného „na LIVE“ / „deploy live“ od uživatele.
- Po dokončení vypiš checklist „hotovo / čeká na tebe“.

---

## Konstanty projektu

| Položka | Hodnota |
|---------|---------|
| GitHub repo | `Hakliano/Ulov_Rezervace` |
| Clone SSH | `git@github.com:Hakliano/Ulov_Rezervace.git` |
| Clone HTTPS | `https://github.com/Hakliano/Ulov_Rezervace.git` |
| Lokální cesta | `~/Projekty/Ulov_Rezervace` |
| Větev denní práce | `dev` |
| Větev LIVE | `main` |
| Hetzner SSH | `root@49.13.23.65` |
| Server app root | `/opt/ulov` |
| Staging URL | `https://www.staging.ulovklienty.cz/` |
| LIVE URL | `https://www.ulovklienty.cz/` |
| Staging deploy | `bash deploy/deploy-staging.sh origin/dev` |
| LIVE deploy | `bash deploy/deploy-live.sh origin/main` |

Pipeline:

```
LOCAL → GitHub DEV → Hetzner Staging (Copy DTB)
         ↓ po schválení
       GitHub MAIN → Hetzner LIVE (ostrá DTB)
```

---

## Fáze 0 — Detekce prostředí

Spusť a zapiš výsledky:

```bash
uname -s
sw_vers
which git || true
which brew || true
which gh || true
which ssh || true
ls -la ~/.ssh 2>/dev/null || true
test -d ~/Projekty/Ulov_Rezervace && echo "REPO_EXISTS" || echo "REPO_MISSING"
```

Pokud nejsi na macOS (`Darwin`), zastav a řekni to uživateli.

---

## Fáze 1 — Nástroje

### 1.1 Xcode CLT (git)

```bash
xcode-select -p || xcode-select --install
```

Pokud vyskočí GUI instalátor, řekni uživateli ať dokončí instalaci a pak pokračuj.

### 1.2 Homebrew

```bash
which brew || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Na Apple Silicon po instalaci doplň PATH (pokud `brew` není v PATH):

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

### 1.3 Balíčky

```bash
brew install git gh
```

Ověř:

```bash
git --version
gh --version
```

---

## Fáze 2 — GitHub autentizace

Preferuj **SSH**. Fallback: HTTPS + `gh auth login`.

### 2.1 SSH klíč pro GitHub

Pokud neexistuje `~/.ssh/id_ed25519_github`:

```bash
ssh-keygen -t ed25519 -C "jirka-macbook-github" -f ~/.ssh/id_ed25519_github -N ""
```

### 2.2 ssh-agent + config

Doplň/vytvoř `~/.ssh/config` (merge, nepřepisuj cizí Host bloky):

```text
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_ed25519_github
  IdentitiesOnly yes
  AddKeysToAgent yes
  UseKeychain yes
```

Pak:

```bash
eval "$(ssh-agent -s)"
ssh-add --apple-use-keychain ~/.ssh/id_ed25519_github
pbcopy < ~/.ssh/id_ed25519_github.pub
echo "PUBLIC_KEY_COPIED_TO_CLIPBOARD"
cat ~/.ssh/id_ed25519_github.pub
```

### 2.3 STOP — uživatel musí přidat klíč na GitHub

Řekni uživateli:

1. Otevři https://github.com/settings/keys
2. **New SSH key**
3. Title: `MacBook Ulov`
4. Vlož obsah z clipboardu / výpisu `*.pub`
5. Save
6. Napiš do chatu: **hotovo GitHub SSH**

Po potvrzení otestuj:

```bash
ssh -T git@github.com
```

Očekávaný úspěch obsahuje `successfully authenticated`.

### 2.4 Fallback HTTPS (jen když SSH selže)

```bash
gh auth login -h github.com -p https -w
gh auth status
```

---

## Fáze 3 — Clone repo

```bash
mkdir -p ~/Projekty
cd ~/Projekty

if [ -d Ulov_Rezervace/.git ]; then
  cd Ulov_Rezervace
  git fetch --all --prune
else
  git clone git@github.com:Hakliano/Ulov_Rezervace.git
  cd Ulov_Rezervace
fi

git checkout dev
git pull origin dev
git branch -vv
git remote -v
git log -1 --oneline
```

Pokud clone přes SSH selže a HTTPS funguje:

```bash
git clone https://github.com/Hakliano/Ulov_Rezervace.git
```

Otevři projekt v Cursoru (řekni uživateli):

**File → Open Folder → `~/Projekty/Ulov_Rezervace`**

Po otevření znovu načti rule `.cursor/rules/deploy-safety.mdc`.

---

## Fáze 4 — Git identity (lokální, ne global config force)

Zkontroluj:

```bash
git config user.name || true
git config user.email || true
```

Pokud chybí, **zeptej se** uživatele na jméno a e-mail a nastav jen v tomto repu:

```bash
git config user.name "JMÉNO"
git config user.email "EMAIL"
```

Nepoužívej `git config --global` bez výslovného souhlasu.

---

## Fáze 5 — SSH na Hetzner (deploy)

### 5.1 Klíč pro server

Pokud neexistuje `~/.ssh/id_ed25519_hetzner`:

```bash
ssh-keygen -t ed25519 -C "jirka-macbook-hetzner" -f ~/.ssh/id_ed25519_hetzner -N ""
```

Doplň do `~/.ssh/config`:

```text
Host ulov
  HostName 49.13.23.65
  User root
  IdentityFile ~/.ssh/id_ed25519_hetzner
  IdentitiesOnly yes
```

```bash
pbcopy < ~/.ssh/id_ed25519_hetzner.pub
cat ~/.ssh/id_ed25519_hetzner.pub
```

### 5.2 STOP — uživatel musí přidat klíč na server

Řekni uživateli (z PC, kde už SSH funguje, nebo z Hetzner Console):

```bash
# Na stroji, který už má přístup:
ssh -i ~/.ssh/id_ed25519 root@49.13.23.65
echo 'VLOŽ_OBSAH_id_ed25519_hetzner.pub' >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
```

Nebo: Hetzner Cloud Console → server → přidat SSH key.

Až uživatel napíše **hotovo Hetzner SSH**, otestuj:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 ulov "hostname; cd /opt/ulov && git rev-parse --short HEAD && git status -sb"
```

Úspěch = výpis hostname + short SHA bez hesla.

Pokud BatchMode selže, nezkoušej hádat hesla — zastav a oprav klíč.

---

## Fáze 6 — Ověření pipeline příkazů (bez deploye)

Jen dry kontrola, **nespouštěj** deploy skripty v této fázi:

```bash
cd ~/Projekty/Ulov_Rezervace
git fetch origin
git rev-parse --short origin/dev
git rev-parse --short origin/main
test -f deploy/deploy-staging.sh && echo STAGING_SCRIPT_OK
test -f deploy/deploy-live.sh && echo LIVE_SCRIPT_OK
ssh ulov "test -x /opt/ulov/deploy/deploy-staging.sh && test -x /opt/ulov/deploy/deploy-live.sh && echo SERVER_SCRIPTS_OK"
```

---

## Fáze 7 — Závěrečný report uživateli

Vypiš přesně:

```text
=== MACBOOK SETUP HOTOVÝ ===
Repo:     ~/Projekty/Ulov_Rezervace
Branch:   dev (denní práce)
GitHub:   OK / CHYBÍ
Hetzner:  OK / CHYBÍ
origin/dev:  <sha>
origin/main: <sha>

Denní práce:
  git checkout dev && git pull
  …úpravy…
  git add … && git commit -m "…" && git push origin dev

Staging:
  ssh ulov 'cd /opt/ulov && bash deploy/deploy-staging.sh origin/dev'
  test: https://www.staging.ulovklienty.cz/

LIVE (jen po schválení):
  git push origin dev:main
  ssh ulov 'cd /opt/ulov && bash deploy/deploy-live.sh origin/main'
  test: https://www.ulovklienty.cz/

ZAKÁZÁNO:
  - scp/rsync z Macu do /opt/ulov/www/
  - commit přímo na main bez stagingu
  - LIVE deploy bez výslovného souhlasu
```

---

## Denní workflow (po setupu) — když uživatel pracuje

### Push na DEV

```bash
cd ~/Projekty/Ulov_Rezervace
git checkout dev
git pull origin dev
# …změny…
git status
git add <relevantní soubory>
git commit -m "…"
git push origin dev
```

### Deploy staging (po „nasaď staging“ / „push + staging“)

```bash
ssh ulov 'cd /opt/ulov && sed -i "s/\r$//" deploy/deploy-staging.sh && bash deploy/deploy-staging.sh origin/dev'
```

Smoke: staging hub + změněné cesty → HTTP 200.

### Deploy LIVE (jen po výslovném „na LIVE“ / „jdi live“)

```bash
cd ~/Projekty/Ulov_Rezervace
git push origin dev:main
ssh ulov 'cd /opt/ulov && sed -i "s/\r$//" deploy/deploy-live.sh && bash deploy/deploy-live.sh origin/main'
```

Pokud smoke ukáže `api_health:502`, reload nginx:

```bash
ssh ulov 'cd /opt/ulov && docker compose exec -T nginx nginx -s reload'
```

Pak znovu curl health + hub.

### Sync s Windows PC

Před prací: `git pull origin dev`  
Před odchodem: `git push origin dev`  
Žádné kopírování `.git` přes USB.

---

## Zakázané akce (vždy)

- `rsync --delete` / přímý sync do LIVE `www/` mimo `deploy-live.sh`
- `git reset --hard` na produkci bez zálohy / souhlasu
- Přepis `www/salonN/` nebo `www/presentace/` neúplnou složkou (bez `index.html`)
- Commit `backend/db.sqlite3`, `.env*`, privátních klíčů, `__pycache__`
- Force push na `main` / `dev` bez výslovného souhlasu

Reference v repu po clonu:
- `.cursor/rules/deploy-safety.mdc`
- `deploy/DEPLOY_PIPELINE.md`
- `deploy/DEPLOY_SAFETY.md`
