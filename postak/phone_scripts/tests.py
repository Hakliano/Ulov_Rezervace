import json
import re

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from phone_scripts.constants import ALL_BRANCH_KEYS, branch_key
from phone_scripts.constants import SalesStyle, WebStatus
from phone_scripts.demo_content import (
    build_stress_payload,
    demo_hya_payload,
    demo_modernik_payload,
)
from phone_scripts.services.import_export import import_script_from_dict
from phone_scripts.services.snapshot import publish_script, build_snapshot
from phone_scripts.services.validate import validate_script


@override_settings(POSTAK_PREFIX='')
class PhoneScriptsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('tel', password='x')
        self.client = Client()
        self.client.login(username='tel', password='x')

    def _publish_demo(self):
        script = import_script_from_dict(demo_modernik_payload(), replace=True)
        ok, errors = publish_script(script)
        self.assertTrue(ok, errors)
        script.refresh_from_db()
        return script

    def test_demo_has_all_branches(self):
        script = self._publish_demo()
        snap = script.published_snapshot
        for web in WebStatus.values:
            for style in SalesStyle.values:
                key = branch_key(web, style)
                self.assertIn(key, snap['initialBranches'])

    def test_validation_rejects_missing_target(self):
        from phone_scripts.models import AnswerOption, ScriptStep

        script = self._publish_demo()
        step = ScriptStep.objects.filter(script=script).first()
        AnswerOption.objects.create(step=step, label='rozbité', sort_order=99)
        result = validate_script(script)
        self.assertFalse(result.ok)

    def test_snapshot_api_requires_login(self):
        url = reverse('telefonni_klikacka_snapshot', kwargs={'slug': 'demo-modernik'})
        anon = Client()
        self.assertEqual(anon.get(url).status_code, 302)
        script = self._publish_demo()
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertEqual(payload['meta']['slug'], script.slug)
        version_url = reverse(
            'telefonni_klikacka_snapshot_version',
            kwargs={'version_id': script.current_version_id},
        )
        res2 = self.client.get(version_url)
        self.assertEqual(res2.status_code, 200)

    def test_prep_page_loads(self):
        self._publish_demo()
        res = self.client.get(reverse('telefonni_klikacka'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Telefonní klikačka')

    def test_prep_page_json_script_is_valid(self):
        """Regrese: data pro JS nesmí procházet escapejs v HTML atributu (rozbije JSON.parse)."""
        script_m = import_script_from_dict(demo_modernik_payload(), replace=True)
        script_h = import_script_from_dict(demo_hya_payload(), replace=True)
        publish_script(script_m)
        publish_script(script_h)
        res = self.client.get(reverse('telefonni_klikacka'))
        html = res.content.decode()
        self.assertIn('id="phone-clicker-config"', html)
        self.assertNotIn('data-scripts=', html)
        match = re.search(
            r'<script[^>]+id="phone-clicker-config"[^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(match, 'Chybí json_script blok phone-clicker-config')
        config = json.loads(match.group(1))
        self.assertIn('scenarios', config)
        self.assertIn('snapshotUrlTemplate', config)
        self.assertIn('defaultAgentName', config)
        products = {item['product'] for item in config['scenarios']}
        self.assertIn('modernik', products)
        self.assertIn('hereyouare', products)

    def test_stress_script_publish_180_steps(self):
        data = build_stress_payload(steps_count=180)
        script = import_script_from_dict(data, replace=True)
        ok, errors = publish_script(script)
        self.assertTrue(ok, errors)
        self.assertGreaterEqual(len(script.published_snapshot['steps']), 181)

    def test_initial_branches_match_sales_style_in_demo_payload(self):
        """Regrese: klíče větví musí odpovídat obsahu vstupních kroků (referenční demo payload)."""
        data = demo_modernik_payload()
        for web in WebStatus.values:
            for style in SalesStyle.values:
                key = branch_key(web, style)
                sid = data['initialBranches'][key]
                say = data['steps'][sid]['say'].lower()
                if style == SalesStyle.DYNAMIC:
                    self.assertIn('přímo', say, msg=f'{key} -> {sid}')
                else:
                    self.assertIn('klidu', say, msg=f'{key} -> {sid}')
                if web == WebStatus.HAS_WEB:
                    self.assertIn('web', say, msg=f'{key} -> {sid}')
                if web == WebStatus.NO_WEB:
                    self.assertTrue('nemá' in say or 'nevidím' in say, msg=f'{key} -> {sid}')

    def test_publish_increments_version(self):
        script = self._publish_demo()
        v1 = script.version
        ok, _ = publish_script(script)
        script.refresh_from_db()
        self.assertTrue(ok)
        self.assertEqual(script.version, v1 + 1)
