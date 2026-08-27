from datetime import datetime, time, timedelta

from django.test import TestCase
from django.utils import timezone

from rezervace.models import Rezervace, RezervacniNastaveni, Zamestnanec, ZamestnanecRozvrh
from rezervace.services.availability import prirad_zamestnance
from salons.models import OteviraciDoba, Salon


def _pristi_pondeli():
    d = timezone.localdate() + timedelta(days=1)
    while d.weekday() != 0:
        d += timedelta(days=1)
    return d


class PrirazeniKdokolivTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(name='Salon Kdokoliv')
        for den in range(7):
            OteviraciDoba.objects.create(
                salon=self.salon, den=den, od=time(9, 0), do=time(17, 0), zavreno=False,
            )
        RezervacniNastaveni.objects.create(
            salon=self.salon,
            interval_minut=30,
            min_predstih_hodin=0,
            max_predstih_mesicu=3,
        )
        self.andrej = self._zamestnanec('Andrej', 0)
        self.bohdan = self._zamestnanec('Bohdan', 1)
        self.cyril = self._zamestnanec('Cyril', 2)
        self.pondeli = _pristi_pondeli()
        self.start = timezone.make_aware(datetime.combine(self.pondeli, time(10, 0)))
        self.end = self.start + timedelta(hours=1)

    def _zamestnanec(self, jmeno, poradi):
        z = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno=jmeno,
            role=Zamestnanec.ROLE_ZAMESTNANEC,
            aktivni=True,
            poradi=poradi,
            prihlasovaci_jmeno=f'{jmeno.lower()}-kdokoliv@test.local',
        )
        for den in range(5):
            ZamestnanecRozvrh.objects.create(
                zamestnanec=z, den=den, od=time(9, 0), do=time(17, 0), volno=False,
            )
        return z

    def _rezervace(self, zamestnanec, zacatek, delka_hodin=1, stav='potvrzeno'):
        return Rezervace.objects.create(
            salon=self.salon,
            zamestnanec=zamestnanec,
            zacatek=zacatek,
            konec=zacatek + timedelta(hours=delka_hodin),
            stav=stav,
            jmeno_host=zamestnanec.jmeno,
        )

    def test_vsichni_volni_dostane_prvniho_v_poradi(self):
        z = prirad_zamestnance(self.salon, self.pondeli, self.start, self.end)
        self.assertEqual(z, self.andrej)

    def test_po_andrejovi_dostane_priste_bohdana(self):
        minuly = timezone.make_aware(datetime.combine(self.pondeli - timedelta(days=7), time(10, 0)))
        self._rezervace(self.andrej, minuly)
        z = prirad_zamestnance(self.salon, self.pondeli, self.start, self.end)
        self.assertEqual(z, self.bohdan)

    def test_po_andrejovi_a_bohdanovi_dostane_cyrila(self):
        minuly = timezone.make_aware(datetime.combine(self.pondeli - timedelta(days=7), time(10, 0)))
        starsi = timezone.make_aware(datetime.combine(self.pondeli - timedelta(days=14), time(10, 0)))
        self._rezervace(self.andrej, minuly)
        self._rezervace(self.bohdan, starsi)
        z = prirad_zamestnance(self.salon, self.pondeli, self.start, self.end)
        self.assertEqual(z, self.cyril)

    def test_nizsi_vytez_ten_den_vyhraje(self):
        odpoledne = timezone.make_aware(datetime.combine(self.pondeli, time(14, 0)))
        self._rezervace(self.andrej, odpoledne, delka_hodin=3)
        self._rezervace(self.bohdan, odpoledne, delka_hodin=1)
        z = prirad_zamestnance(self.salon, self.pondeli, self.start, self.end)
        self.assertEqual(z, self.cyril)

    def test_vybrany_zamestnanec_se_respektuje(self):
        z = prirad_zamestnance(
            self.salon, self.pondeli, self.start, self.end, preferovany_id=self.cyril.id,
        )
        self.assertEqual(z, self.cyril)

    def test_storno_se_do_vyteze_nepocita(self):
        rano = timezone.make_aware(datetime.combine(self.pondeli, time(9, 0)))
        self._rezervace(self.andrej, rano, delka_hodin=4, stav='zakaznik_storno')
        z = prirad_zamestnance(self.salon, self.pondeli, self.start, self.end)
        self.assertEqual(z, self.andrej)
