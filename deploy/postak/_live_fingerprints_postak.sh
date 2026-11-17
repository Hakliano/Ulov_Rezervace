#!/usr/bin/env bash
set -eu
TS="${1:-pre}"
OUT="/root/postak_fingerprints_${TS}.txt"
{
  echo "=== $TS $(date -Iseconds) ==="
  docker exec -w /app ulov-live-postak python manage.py shell -c "
from jadro.klienti_models import KlientModernik, KlientHya, KlientSyncMeta
for pk in ('sync_modernik_delta','sync_hya_delta'):
    m = KlientSyncMeta.objects.filter(pk=pk).first()
    print(pk, m.posledni_delta if m else None, 'chyba', (m.posledni_chyba or '')[:120] if m else '')
print('mod_count', KlientModernik.objects.count())
print('hya_count', KlientHya.objects.count())
"
  docker exec postak-live-db-1 psql -U postak -d postak_live -tAc "SELECT md5(string_agg(remote_id::text||coalesce(email,'')||coalesce(telefon,''), '|' ORDER BY remote_id)) FROM jadro_klientmodernik"
  docker exec postak-live-db-1 psql -U postak -d postak_live -tAc "SELECT md5(string_agg(remote_id::text||coalesce(email,'')||coalesce(telefon,''), '|' ORDER BY remote_id)) FROM jadro_klienthya"
} >"$OUT"
echo "wrote $OUT"
cat "$OUT"