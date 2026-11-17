from django.test import TestCase

from jadro.obchodni_stavy import (
    kanon_do_hya_api,
    kanon_do_modernik,
    kanon_z_api_stavu,
    stavy_spolecne_pro_ui,
)


class ObchodniStavyTests(TestCase):
    def test_14_stavu_v_ui(self):
        self.assertEqual(len(stavy_spolecne_pro_ui()), 14)

    def test_hya_api_obousmerne(self):
        for canon, label in [
            ('lead_pred_webu', 'x'),
            ('prodano', 'x'),
            ('nechceme', 'x'),
        ]:
            api = kanon_do_hya_api(canon)
            self.assertEqual(kanon_z_api_stavu(api), canon)
            self.assertEqual(kanon_do_modernik(canon), canon)

    def test_modernik_kanon_bez_mapovani(self):
        self.assertEqual(kanon_do_modernik('ma_zajem'), 'ma_zajem')