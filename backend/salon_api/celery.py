"""Celery aplikace pro ULOV KLIENTY (fronta e-mailů)."""

import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'salon_api.settings')

app = Celery('salon_api')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
