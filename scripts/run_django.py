"""Run Django management commands from the project root.

Why this exists: this machine's embeddable Python 3.13 ships a
``python313._pth`` file that enables *isolated mode*. In isolated mode Python
builds ``sys.path`` only from that file (which points at an unrelated project,
``C:\\microjobs.site``) and ignores both PYTHONPATH and the current directory.
That makes ``config`` unimportable, so ``manage.py`` fails with
"ModuleNotFoundError: No module named 'config'".

Rather than editing that shared Python install, this launcher puts the project
root on ``sys.path`` first and then hands off to Django's own entry point.

Usage (from the project root, no need to activate anything):
    python scripts/run_django.py test tests.integration pdf_tools
    python scripts/run_django.py check
    python scripts/run_django.py migrate
"""
import os
import sys

# Project root = parent of the directory holding this file.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')


def main():
    from django.core.management import execute_from_command_line

    # Strip the launcher name so Django sees its own argv.
    execute_from_command_line([sys.argv[0]] + sys.argv[1:])


if __name__ == '__main__':
    main()
