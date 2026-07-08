"""Jednoduchý load test veřejných (read-only) endpointů rezervací.

Měří odezvu API pod zátěží 50 / 100 souběžných uživatelů. Netvoří rezervace
(neplní DB, nenaráží na throttling) — simuluje běžné prohlížení volných termínů.

Instalace a spuštění (na testovacím prostředí, ne na ostrém provozu):

    pip install locust
    # 50 uživatelů:
    locust -f deploy/loadtest/locustfile.py --host https://api.vase-domena.cz \\
           --users 50 --spawn-rate 10 --run-time 2m --headless
    # 100 uživatelů:
    locust -f deploy/loadtest/locustfile.py --host https://api.vase-domena.cz \\
           --users 100 --spawn-rate 20 --run-time 2m --headless

Sledujte současně na serveru:  docker stats   (CPU / RAM kontejnerů).

Nastavení přes proměnné prostředí:
    SALON_ID   – které salon ID testovat (default 1)
"""

import datetime
import os
import random

from locust import HttpUser, between, task

SALON_ID = os.environ.get('SALON_ID', '1')


class RezervacniUzivatel(HttpUser):
    wait_time = between(1, 3)

    @task(1)
    def info(self):
        self.client.get(
            f'/api/salon/{SALON_ID}/rezervace/info/',
            name='rezervace/info',
        )

    @task(3)
    def volne_terminy(self):
        den = datetime.date.today() + datetime.timedelta(days=random.randint(1, 14))
        self.client.get(
            f'/api/salon/{SALON_ID}/rezervace/volne-terminy/?datum={den.isoformat()}',
            name='rezervace/volne-terminy',
        )

    @task(1)
    def web_salonu(self):
        self.client.get(f'/api/salon/{SALON_ID}/', name='salon/detail')
