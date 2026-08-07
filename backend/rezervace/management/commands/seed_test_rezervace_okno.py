"""
Doplní testovací rezervace do LIVE/staging kalendáře.

Pravidlo: pro každý den v intervalu, kde má salon alespoň 1 aktivního
pracovníka (ne Manager) s rozvrhem (ne volno), zajistí min. N rezervací.
Nepřepisuje existující — jen doplní chybějící počet.
Neposílá e-maily (přímý ORM create, stav potvrzena, bez notifikací).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone

from rezervace.models import Rezervace, RezervaceSluzba, Zamestnanec, ZamestnanecAbsence
from salons.models import CenikPolozka, Salon

TZ = ZoneInfo('Europe/Prague')
JMENA = [
    'Anna Nováková', 'Petra Svobodová', 'Jana Dvořáková', 'Eva Černá',
    'Lucie Procházková', 'Martina Kučerová', 'Tereza Veselá', 'Kateřina Horáková',
    'Veronika Němcová', 'Barbora Pokorná', 'Markéta Králová', 'Simona Benešová',
]


class Command(BaseCommand):
    help = 'Doplní min. N testovacích rezervací na pracovní dny v okně (default salon 2+5).'

    def add_arguments(self, parser):
        parser.add_argument('--salon', type=int, action='append', dest='salony',
                            help='Salon ID (lze vícekrát). Default: 2 a 5.')
        parser.add_argument('--from', dest='date_from', default='2026-08-07')
        parser.add_argument('--to', dest='date_to', default='2026-08-16')
        parser.add_argument('--min', dest='min_count', type=int, default=4)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        salon_ids = options['salony'] or [2, 5]
        d0 = date.fromisoformat(options['date_from'])
        d1 = date.fromisoformat(options['date_to'])
        min_n = max(1, int(options['min_count']))
        dry = bool(options['dry_run'])

        total_created = 0
        for sid in salon_ids:
            try:
                salon = Salon.objects.get(pk=sid)
            except Salon.DoesNotExist:
                self.stderr.write(f'Salon {sid} neexistuje — skip')
                continue
            created = self._seed_salon(salon, d0, d1, min_n, dry)
            total_created += created
            self.stdout.write(
                self.style.SUCCESS(f'{salon.name} (id={sid}): +{created} rezervací')
            )
        self.stdout.write(self.style.SUCCESS(f'Hotovo celkem +{total_created}'))

    def _seed_salon(self, salon: Salon, d0: date, d1: date, min_n: int, dry: bool) -> int:
        staff = list(
            Zamestnanec.objects.filter(salon=salon, aktivni=True)
            .exclude(role='majitel')
            .prefetch_related('rozvrh')
        )
        if not staff:
            self.stderr.write(f'  {salon.name}: žádný Staff — skip')
            return 0

        sluzby = list(
            CenikPolozka.objects.filter(salon=salon, aktivni=True).order_by('poradi', 'id')
        )
        if not sluzby:
            self.stderr.write(f'  {salon.name}: žádná služba — skip')
            return 0

        created = 0
        day = d0
        name_i = 0
        while day <= d1:
            weekday = day.weekday()  # 0=po … 6=ne — shodné s ZamestnanecRozvrh.den
            working = self._working_staff(staff, day, weekday)
            if not working:
                day += timedelta(days=1)
                continue

            existing = (
                Rezervace.objects.filter(salon=salon, zacatek__date=day)
                .exclude(stav='zruseno')
                .count()
            )
            need = max(0, min_n - existing)
            if need == 0:
                day += timedelta(days=1)
                continue

            slots = self._candidate_slots(working, day, need + 8)
            used = 0
            for zam, start, end in slots:
                if used >= need:
                    break
                if self._slot_taken(salon, zam, start, end):
                    continue
                jmeno = JMENA[name_i % len(JMENA)]
                name_i += 1
                sluzba = sluzby[used % len(sluzby)]
                if dry:
                    self.stdout.write(
                        f'  DRY {day} {start:%H:%M}-{end:%H:%M} {zam.jmeno} · {jmeno}'
                    )
                else:
                    rez = Rezervace.objects.create(
                        salon=salon,
                        zamestnanec=zam,
                        zacatek=start,
                        konec=end,
                        stav='potvrzena',
                        typ_vytvoreni='telefon',
                        jmeno_host=jmeno,
                        email_host=f'test.{salon.pk}.{day:%Y%m%d}.{used}@ulov.local',
                        poznamka_interni='TEST seed 2026-08 (LIVE demo data)',
                        notifikace_odeslane=['seed_skip'],
                    )
                    RezervaceSluzba.objects.create(rezervace=rez, sluzba=sluzba, poradi=0)
                used += 1
                created += 1
            if used < need:
                self.stderr.write(
                    f'  {salon.name} {day}: jen {used}/{need} (málo volných slotů)'
                )
            day += timedelta(days=1)
        return created

    def _working_staff(self, staff, day: date, weekday: int):
        out = []
        for z in staff:
            if ZamestnanecAbsence.objects.filter(
                zamestnanec=z,
                stav=ZamestnanecAbsence.STAV_SCHVALENO,
                datum_od__lte=day,
                datum_do__gte=day,
            ).exists():
                continue
            roz = next((r for r in z.rozvrh.all() if r.den == weekday), None)
            if not roz or roz.volno or not roz.od or not roz.do:
                continue
            out.append((z, roz))
        return out

    def _candidate_slots(self, working, day: date, limit: int):
        """Střídá pracovníky, sloty po 90 min od začátku směny (+15 min offset)."""
        slots = []
        for round_i in range(12):
            for z, roz in working:
                start_t = (
                    datetime.combine(day, roz.od, tzinfo=TZ)
                    + timedelta(minutes=15 + round_i * 90)
                )
                dur = 45
                end_t = start_t + timedelta(minutes=dur)
                end_limit = datetime.combine(day, roz.do, tzinfo=TZ)
                if end_t > end_limit:
                    continue
                slots.append((z, start_t, end_t))
                if len(slots) >= limit:
                    return slots
        return slots

    def _slot_taken(self, salon, zam, start, end) -> bool:
        return Rezervace.objects.filter(
            salon=salon,
            zamestnanec=zam,
        ).filter(
            Q(zacatek__lt=end) & Q(konec__gt=start),
        ).exclude(stav='zruseno').exists()
