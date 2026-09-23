"""Link chart of accounts parent relationships from account code hierarchy."""
from django.core.management.base import BaseCommand

from apps.finance.coa_utils import link_account_parents


class Command(BaseCommand):
    help = 'Set parent account links based on account code hierarchy (e.g. 1010 -> 1000).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show how many accounts would be updated without saving',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        updated = link_account_parents(dry_run=dry_run)

        if dry_run:
            self.stdout.write(self.style.WARNING(f'Would update {updated} account(s).'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Updated {updated} account(s).'))
