from django.db import migrations
from django.contrib.auth.hashers import make_password

def create_admin(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    if not User.objects.filter(username='admin').exists():
        User.objects.create(
            username='admin',
            email='admin@taskflow.app',
            password=make_password('admin123'),
            is_staff=True,
            is_superuser=True,
            is_active=True
        )

class Migration(migrations.Migration):
    dependencies = [('tasks', '0001_initial')]
    operations = [migrations.RunPython(create_admin)]