import json
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'salon_api.settings')

import django

django.setup()

from django.test import RequestFactory

from flow.emails import generate_heslo
from flow.models import FlowSession, FlowUser, heslo_je_platne
from flow.views import FlowPrihlaseniView
from rezervace.models import Zamestnanec
from salons.models import Salon

rf = RequestFactory()
req = rf.post(
    '/api/flow/prihlaseni/',
    data=json.dumps({'email': 'x@y.cz', 'password': 'bad'}),
    content_type='application/json',
)
resp = FlowPrihlaseniView.as_view()(req)
print('login_bad', resp.status_code, resp.data)

salon = Salon.objects.get(pk=1)
z = (
    Zamestnanec.objects.filter(salon=salon, role='zamestnanec').first()
    or Zamestnanec.objects.filter(salon=salon).first()
)
assert z, 'salon 1 has no staff'
FlowUser.objects.filter(email='flow.test.local@example.com').delete()
if hasattr(z, 'flow_ucet'):
    try:
        z.flow_ucet.delete()
    except FlowUser.DoesNotExist:
        pass

u = FlowUser(
    salon=salon,
    zamestnanec=z,
    email='flow.test.local@example.com',
    visible_overview=True,
    aktivni=True,
)
u.set_password('Testflow1')
u.save()

req2 = rf.post(
    '/api/flow/prihlaseni/',
    data=json.dumps({'email': 'flow.test.local@example.com', 'password': 'Testflow1'}),
    content_type='application/json',
)
resp2 = FlowPrihlaseniView.as_view()(req2)
print('login_ok', resp2.status_code, sorted(resp2.data.keys()))
assert resp2.status_code == 200
assert 'token' in resp2.data

FlowSession.objects.filter(user=u).delete()
u.delete()
print('pwd_gen_ok', heslo_je_platne(generate_heslo(12)))
print('staff_sample', z.id, z.jmeno)
print('OK')
