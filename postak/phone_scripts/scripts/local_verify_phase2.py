"""LOCAL kontrola fáze 2. Spuštění: python manage.py shell -c \"exec(open('phone_scripts/scripts/local_verify_phase2.py', encoding='utf-8').read())\""""

import json

import re

import sys

from pathlib import Path



from django.conf import settings

from django.contrib.auth.models import User

from django.test import Client, override_settings

from django.urls import reverse



from phone_scripts.constants import VersionStatus

from phone_scripts.models import PhoneScript

from phone_scripts.services.validate_snapshot import validate_snapshot_payload

from phone_scripts.services.versions import (

    create_script_with_draft,

    import_new_draft_version,

    parse_uploaded_json,

    publish_version,

)



checks: list[tuple[str, bool, str]] = []

_hosts = list(settings.ALLOWED_HOSTS) + ['testserver', 'localhost', '127.0.0.1']





def ok(name: str, cond: bool, detail: str = '') -> None:

    checks.append((name, cond, detail))

    print('OK' if cond else 'FAIL', name, detail)





admin, _ = User.objects.get_or_create(

    username='hakl@modernik.cz',

    defaults={'email': 'hakl@modernik.cz'},

)

admin.is_superuser = True

admin.is_active = True

admin.save()

if not admin.check_password('Layla12345!!'):

    admin.set_password('Layla12345!!')

    admin.save()



tel, _ = User.objects.get_or_create(username='verify-tel-local')

tel.is_active = True

tel.save()



with override_settings(ALLOWED_HOSTS=_hosts):

    c_admin = Client()

    c_admin.login(username=admin.username, password='Layla12345!!')

    c_user = Client()

    c_user.force_login(tel)



    for slug in ('demo-modernik', 'demo-hereyouare'):

        s = PhoneScript.objects.filter(slug=slug).first()

        ok(f'demo {slug} existuje', s is not None)

        if s:

            ok(f'demo {slug} aktivní', s.is_active)

            ok(f'demo {slug} má current_version', bool(s.current_version_id))

            ok(

                f'demo {slug} má snapshot',

                bool(s.current_version and s.current_version.snapshot.get('steps')),

            )



    r = c_admin.get(reverse('telefonni_klikacka_sprava_seznam'))

    ok('dashboard superuser HTTP 200', r.status_code == 200)



    r = c_user.get(reverse('telefonni_klikacka_sprava_seznam'))

    ok('dashboard běžný uživatel zamítnut', r.status_code in (403, 302))



    r = c_admin.get(reverse('telefonni_klikacka'))

    ok('klikačka superuser HTTP 200', r.status_code == 200)

    match = re.search(

        r'<script[^>]+id="phone-clicker-config"[^>]*>(.*?)</script>',

        r.content.decode(),

        re.DOTALL,

    )

    cfg = json.loads(match.group(1)) if match else {}

    ok('katalog aspon 2 scenaru', len(cfg.get('scenarios', [])) >= 2)



    script = PhoneScript.objects.get(slug='demo-modernik')

    current = script.current_version

    assert current is not None



    r = c_user.get(reverse('telefonni_klikacka_snapshot_version', kwargs={'version_id': current.pk}))

    ok('snapshot pro telefonistu', r.status_code == 200 and 'steps' in r.json())



    draft = import_new_draft_version(script, current.snapshot, user=admin, note='LOCAL verify koncept')

    r = c_user.get(reverse('telefonni_klikacka_snapshot_version', kwargs={'version_id': draft.pk}))

    ok('koncept telefonista 403', r.status_code == 403)

    r = c_admin.get(reverse('telefonni_klikacka_snapshot_version', kwargs={'version_id': draft.pk}))

    ok('koncept superuser 200', r.status_code == 200)



    export_path = Path('phone_scripts/fixtures/demo-modernik.export.json')

    payload = parse_uploaded_json(export_path.read_bytes())

    val = validate_snapshot_payload(payload)

    ok('JSON export validní', val.ok, ' | '.join(val.errors))

    slug = 'local-verify-import'

    PhoneScript.objects.filter(slug=slug).delete()

    test_script, draft_ver = create_script_with_draft(

        name='Verify import',

        slug=slug,

        product='modernik',

        snapshot=payload,

        user=admin,

        note='verify',

    )

    ok('import = koncept', draft_ver.status == VersionStatus.DRAFT)

    publish_version(draft_ver)

    test_script.refresh_from_db()

    draft_ver.refresh_from_db()

    ok('publikace nastaví current', test_script.current_version_id == draft_ver.pk)

    ok('po publikaci aktivní', test_script.is_active)



    r = c_admin.get(reverse('telefonni_klikacka_sprava_testovat', kwargs={'version_id': draft_ver.pk}))

    ok('testovat redirect', r.status_code == 302)



    script.refresh_from_db()

    ok('demo-modernik current beze změny', script.current_version_id == current.pk)



    failed = [c for c in checks if not c[1]]

    print('---')

    print(f'Shrnutí: {len(checks) - len(failed)} / {len(checks)}')

    if failed:

        sys.exit(1)


