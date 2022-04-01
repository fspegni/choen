from prompt_toolkit import prompt
from django.core.management.base import BaseCommand, no_translations

from enforcer import cli


class Command(BaseCommand):

    def handle(self, *args, **options):

        cli(*args, **options)
