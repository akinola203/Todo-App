import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'todo_desktop.settings')

app = Celery('todo_desktop')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
