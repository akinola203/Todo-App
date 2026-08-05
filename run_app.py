import os
import sys
import webbrowser
import threading
import time

# Handle PyInstaller bundled paths
def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath('.'), relative_path)

# Set paths BEFORE importing Django
BASE_DIR = get_resource_path('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'todo_desktop.settings')

# CRITICAL: Setup Django apps registry before any management commands
import django
django.setup()

def start_server():
    from django.core.management import execute_from_command_line
    execute_from_command_line(['manage.py', 'runserver', '--noreload'])

def open_browser():
    time.sleep(3)
    webbrowser.open('http://127.0.0.1:8000/')

if __name__ == '__main__':
    from django.core.management import call_command
    call_command('migrate', '--run-syncdb')

    threading.Thread(target=open_browser, daemon=True).start()
    start_server()