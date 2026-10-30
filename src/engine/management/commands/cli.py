from prompt_toolkit import prompt
from django.core.management.base import BaseCommand, no_translations

from enforcer import cli


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            "script",
            nargs="?",
            default=None,
            help="Optional script command"
        )

    def handle(self, *args, **options):
        script = options.pop("script")
        cli(script=script, **options)
