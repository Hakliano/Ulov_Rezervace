#!/usr/bin/env bash
# Kontrola kompletnosti složek před syncem do www/.
# Použití (z kořene repa):
#   bash deploy/pre-deploy-check.sh salon7 salon8 presentace
# Exit 1 = některá složka není vhodná k nasazení.
set -euo pipefail

cd "$(dirname "$0")/.."
fail=0

if [ "$#" -eq 0 ]; then
  echo "Použití: bash deploy/pre-deploy-check.sh <složka> [složka...]"
  echo "Příklad: bash deploy/pre-deploy-check.sh salon1 salon7 presentace"
  exit 2
fi

for d in "$@"; do
  if [ ! -d "$d" ]; then
    echo "FAIL  $d  — složka neexistuje"
    fail=1
    continue
  fi
  missing=()
  [ -f "$d/index.html" ] || missing+=("index.html")
  # u root presentace stačí index; u salon/demo chceme i CSS/JS pokud jde o veřejný web
  if [[ "$d" == salon* ]] || [[ "$d" == zdravi-* ]] || [[ "$d" == remesla-* ]] || [[ "$d" == provoz-* ]] || [[ "$d" == flow ]] || [[ "$d" == partner ]]; then
    [ -f "$d/style.css" ] || missing+=("style.css")
    [ -f "$d/app.js" ] || missing+=("app.js")
  fi
  if [ "${#missing[@]}" -gt 0 ]; then
    echo "FAIL  $d  — chybí: ${missing[*]}  → NESYNCOVAT"
    fail=1
  else
    echo "OK    $d"
  fi
done

if [ "$fail" -ne 0 ]; then
  echo
  echo "Zastaveno. Viz deploy/DEPLOY_SAFETY.md"
  exit 1
fi

echo
echo "Checklist OK — teprve teď záloha + dry-run rsync."
