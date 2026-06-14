from __future__ import annotations

import os
from celery import Celery

# Указываем Django какой settings использовать
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')

app = Celery('mysite')

# Берём настройки из settings.py (все переменные с префиксом CELERY_)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматически находим tasks.py во всех приложениях
app.autodiscover_tasks()