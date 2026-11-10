import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from jadro.bunny_client import BunnyStorageError
from jadro.dokumentace_models import REZIM_MOJE, REZIM_SDILENE, DokumentSlozka, DokumentSoubor

MAIL_KEY = '5UJw-fkaQCvOYE6rjCyROlCttrakyH3-D8Qieby3Mvc='
PDF = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'


@override_settings(POSTAK_PREFIX='', POSTAK_MAIL_ENCRYPTION_KEY=MAIL_KEY)
class DokumentaceTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.tmp.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.tmp.cleanup)
        self.user = User.objects.create_user('eva', password='x')
        self.other = User.objects.create_user('bob', password='x')
        self.su = User.objects.create_superuser('su', password='x')

    def _slozka(self, rezim, nazev, user=None, parent=None):
        return DokumentSlozka.objects.create(
            nazev=nazev,
            rezim=rezim,
            parent=parent,
            vlastnik=user if rezim == REZIM_MOJE else None,
            vytvoril=user or self.su,
        )

    def _nahrat(self, client, slozka, nazev='doc.pdf', data=PDF):
        f = SimpleUploadedFile(nazev, data, content_type='application/pdf')
        return client.post(reverse('dokumentace_nahrat'), {'slozka': slozka.pk, 'soubor': f})

    @patch('jadro.dokumentace_services.default_storage.exists')
    def test_stahnout_bez_exists_kontroli(self, exists_mock):
        sl = self._slozka(REZIM_SDILENE, 'Firemni')
        self.client.force_login(self.su)
        self._nahrat(self.client, sl)
        soubor = DokumentSoubor.objects.get()
        exists_mock.side_effect = BunnyStorageError('Bunny HTTP 401')
        r = self.client.get(reverse('dokumentace_stahnout', args=[soubor.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))
        exists_mock.assert_not_called()

    @patch('jadro.dokumentace_services.default_storage.open')
    def test_stahnout_chybejici_soubor_404(self, open_mock):
        sl = self._slozka(REZIM_SDILENE, 'Firemni')
        self.client.force_login(self.su)
        self._nahrat(self.client, sl)
        soubor = DokumentSoubor.objects.get()
        open_mock.side_effect = FileNotFoundError('missing')
        r = self.client.get(reverse('dokumentace_stahnout', args=[soubor.pk]))
        self.assertEqual(r.status_code, 404)

    @patch('jadro.dokumentace_services.default_storage.open')
    def test_stahnout_bunny_chyba_503(self, open_mock):
        sl = self._slozka(REZIM_SDILENE, 'Firemni')
        self.client.force_login(self.su)
        self._nahrat(self.client, sl)
        soubor = DokumentSoubor.objects.get()
        open_mock.side_effect = BunnyStorageError('Bunny HTTP 500')
        r = self.client.get(reverse('dokumentace_stahnout', args=[soubor.pk]))
        self.assertEqual(r.status_code, 503)

    def test_sdilene_cist_vs_sprava(self):
        sl = self._slozka(REZIM_SDILENE, 'Firemni')
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('dokumentace')).status_code, 200)
        r = self.client.post(
            reverse('dokumentace_slozka_nova'),
            {'rezim': REZIM_SDILENE, 'vlastnik': self.user.pk, 'nazev': 'x'},
        )
        self.assertEqual(r.status_code, 403)
        self.client.force_login(self.su)
        self._nahrat(self.client, sl)
        self.assertEqual(DokumentSoubor.objects.count(), 1)
        self.client.force_login(self.user)
        soubor = DokumentSoubor.objects.get()
        dl = self.client.get(reverse('dokumentace_stahnout', args=[soubor.pk]))
        self.assertEqual(dl.status_code, 200)
        self.assertEqual(dl['Content-Disposition'], 'attachment; filename="doc.pdf"')

    def test_soukrome_opravneni(self):
        mine = self._slozka(REZIM_MOJE, 'Moje', user=self.user)
        theirs = self._slozka(REZIM_MOJE, 'Bobovo', user=self.other)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('dokumentace'), {'rezim': 'moje', 'slozka': mine.pk}).status_code, 403)
        self._nahrat(self.client, theirs)
        soubor = DokumentSoubor.objects.get()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('dokumentace_stahnout', args=[soubor.pk])).status_code, 403)
        self.client.force_login(self.su)
        self.assertEqual(self.client.get(reverse('dokumentace_stahnout', args=[soubor.pk])).status_code, 200)

    def test_podslozka_presun_zakaz_do_potomka(self):
        self.client.force_login(self.su)
        root = self._slozka(REZIM_SDILENE, 'A')
        child = self._slozka(REZIM_SDILENE, 'B', parent=root)
        r = self.client.post(
            reverse('dokumentace_slozka_presunout', args=[root.pk]),
            {'cil_parent': child.pk},
        )
        self.assertRedirects(r, reverse('dokumentace') + f'?rezim=sdilene&slozka={root.pk}', fetch_redirect_response=False)
        root.refresh_from_db()
        self.assertIsNone(root.parent_id)

    def test_smazani_obsahu_slozky(self):
        self.client.force_login(self.su)
        sl = self._slozka(REZIM_SDILENE, 'Del')
        self._nahrat(self.client, sl)
        child = self._slozka(REZIM_SDILENE, 'Pod', parent=sl)
        r = self.client.post(reverse('dokumentace_slozka_smazat', args=[sl.pk]), {'potvrdit': '0'})
        self.assertTrue(DokumentSlozka.objects.filter(pk=sl.pk).exists())
        r = self.client.post(reverse('dokumentace_slozka_smazat', args=[sl.pk]), {'potvrdit': '1'})
        self.assertFalse(DokumentSlozka.objects.filter(pk=sl.pk).exists())
        self.assertFalse(DokumentSoubor.objects.exists())

    def test_odmitnuti_souboru(self):
        self.client.force_login(self.su)
        sl = self._slozka(REZIM_SDILENE, 'x')
        big = SimpleUploadedFile('huge.pdf', PDF + b'0' * (21 * 1024 * 1024), content_type='application/pdf')
        self.client.post(reverse('dokumentace_nahrat'), {'slozka': sl.pk, 'soubor': big})
        self.assertFalse(DokumentSoubor.objects.exists())
        exe = SimpleUploadedFile('bad.exe', b'MZfake', content_type='application/octet-stream')
        self.client.post(reverse('dokumentace_nahrat'), {'slozka': sl.pk, 'soubor': exe})
        self.assertFalse(DokumentSoubor.objects.exists())

    def test_prejmenovat_a_presunout_soubor(self):
        self.client.force_login(self.su)
        a = self._slozka(REZIM_SDILENE, 'A')
        b = self._slozka(REZIM_SDILENE, 'B')
        self._nahrat(self.client, a)
        soubor = DokumentSoubor.objects.get()
        self.client.post(reverse('dokumentace_soubor_prejmenovat', args=[soubor.pk]), {'nazev': 'jiny.pdf'})
        soubor.refresh_from_db()
        self.assertEqual(soubor.nazev, 'jiny.pdf')
        self.client.post(reverse('dokumentace_soubor_presunout', args=[soubor.pk]), {'cil_slozka': b.pk})
        soubor.refresh_from_db()
        self.assertEqual(soubor.slozka_id, b.pk)

    def test_media_cesta_neni_verejna(self):
        self.client.force_login(self.su)
        sl = self._slozka(REZIM_SDILENE, 'z')
        self._nahrat(self.client, sl)
        soubor = DokumentSoubor.objects.get()
        rel = soubor.soubor.name.replace('\\', '/')
        r = self.client.get('/media/' + rel)
        self.assertIn(r.status_code, (404, 302, 403))

    def test_prehled_stale_ok(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('prehled')).status_code, 200)

    def test_doc03_vzhled(self):
        self.client.force_login(self.su)
        sl = self._slozka(REZIM_SDILENE, 'UI')
        url = reverse('dokumentace') + f'?rezim=sdilene&slozka={sl.pk}'
        r = self.client.get(url)
        self.assertContains(r, 'doc-tabs-main')
        self.assertContains(r, 'Sdílené dokumenty')
        self.assertContains(r, 'Moje dokumenty')
        self.assertContains(r, 'Maximální velikost souboru: 20 MB')
        self.assertContains(r, 'Máte příliš velký obrázek?')
        self.assertContains(r, 'https://cloudinary.com/tools/image-to-webp')
        self.assertContains(r, 'rel="noopener noreferrer"')
        self.assertContains(r, 'target="_blank"')
        r2 = self.client.get(reverse('dokumentace') + '?rezim=moje')
        self.assertContains(r2, 'doc-tab active')
