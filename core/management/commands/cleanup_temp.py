"""Delete stale files from MEDIA_ROOT/temp.

Usage:
    python manage.py cleanup_temp            # uses TEMP_FILE_MAX_AGE_HOURS
    python manage.py cleanup_temp --age 1    # delete files older than 1 hour

Schedule via cron or a Render cron job, e.g.:
    python manage.py cleanup_temp
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Delete files in MEDIA_ROOT/temp older than the retention window.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--age', type=int, default=None,
            help='Max age in hours (default: settings.TEMP_FILE_MAX_AGE_HOURS).',
        )

    def handle(self, *args, **options):
        from core.middleware import cleanup_temp_files

        age = options['age']
        removed = cleanup_temp_files(max_age_hours=age)
        effective = age if age is not None else getattr(
            settings, 'TEMP_FILE_MAX_AGE_HOURS', 6)
        self.stdout.write(self.style.SUCCESS(
            f'cleanup_temp: removed {removed} file(s) older than {effective}h '
            f'from {os.path.join(settings.MEDIA_ROOT, "temp")}'))
