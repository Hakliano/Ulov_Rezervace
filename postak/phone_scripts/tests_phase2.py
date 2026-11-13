import json
import re

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from phone_scripts.constants import VersionStatus
from phone_scripts.demo_content import demo_modernik_payload
from phone_scripts.models import PhoneScript, PhoneScriptVersion
from phone_scripts.services.import_export import import_script_from_dict
from phone_scripts.services.snapshot import publish_script
from phone_scripts.services.versions import import_new_draft_version, publish_version


@override_settings(POSTAK_PREFIX='')
class PhoneScriptsPhase2Tests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', password='x', is_superuser=True)
        self.user = User.objects.create_user('tel', password='x')
        self.client = Client()
        self.admin_client = Client()
        self.admin_client.login(username='admin', password='x')
        self.client.login(username='tel', password='x')

    def _demo_script(self):
        script = import_script_from_dict(demo_modernik_payload(), replace=True)
        publish_script(script, user=self.admin)
        script.refresh_from_db()
        return script

    def test_two_modernik_scripts_in_catalog(self):
        self._demo_script()
        data = demo_modernik_payload()
        data['meta']['slug'] = 'modernik-alt'
        data['meta']['name'] = 'Moderník alternativa'
        script2 = import_script_from_dict(data, replace=True)
        publish_script(script2, user=self.admin)
        res = self.client.get(reverse('telefonni_klikacka'))
        config = self._parse_config(res)
        modernik = [s for s in config['scenarios'] if s['product'] == 'modernik']
        self.assertEqual(len(modernik), 2)

    def test_user_cannot_access_draft_snapshot(self):
        script = self._demo_script()
        draft = import_new_draft_version(
            script, script.current_version.snapshot, user=self.admin, note='draft'
        )
        url = reverse('telefonni_klikacka_snapshot_version', kwargs={'version_id': draft.pk})
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.admin_client.get(url).status_code, 200)

    def test_import_draft_keeps_published_for_telefonist(self):
        script = self._demo_script()
        current_id = script.current_version_id
        draft = import_new_draft_version(
            script, script.current_version.snapshot, user=self.admin, note='draft'
        )
        script.refresh_from_db()
        self.assertEqual(script.current_version_id, current_id)
        self.assertEqual(draft.status, VersionStatus.DRAFT)

    def test_publish_switches_current_and_archives_old(self):
        script = self._demo_script()
        old = script.current_version
        draft = import_new_draft_version(
            script, script.current_version.snapshot, user=self.admin, note='vnext'
        )
        publish_version(draft)
        old.refresh_from_db()
        script.refresh_from_db()
        self.assertEqual(old.status, VersionStatus.ARCHIVED)
        self.assertEqual(script.current_version_id, draft.pk)

    def test_web_import_invalid_json_rejected(self):
        bad = json.dumps({'steps': {}}).encode()
        f = SimpleUploadedFile('bad.json', bad, content_type='application/json')
        url = reverse('telefonni_klikacka_sprava_import')
        res = self.admin_client.post(
            url,
            {
                'mode': 'new',
                'json_file': f,
                'new_name': 'X',
                'new_slug': 'invalid-x',
                'new_product': 'modernik',
            },
        )
        self.assertFalse(PhoneScript.objects.filter(slug='invalid-x').exists())

    def test_prep_config_uses_scenarios_not_legacy_scripts(self):
        self._demo_script()
        res = self.client.get(reverse('telefonni_klikacka'))
        config = self._parse_config(res)
        self.assertIn('scenarios', config)
        self.assertIn('snapshotUrlTemplate', config)
        self.assertIn('__VERSION_ID__', config['snapshotUrlTemplate'])

    def _parse_config(self, response):
        html = response.content.decode()
        match = re.search(
            r'<script[^>]+id="phone-clicker-config"[^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        return json.loads(match.group(1))
