# myapp/management/commands/runserver.py

from django.contrib.sites.models import Site
from django.core.management.commands.runserver import Command as RunserverCommand

# this custom command allows to update the Site instance with the actual address/port
class Command(RunserverCommand):

    def inner_run(self, *args, **options):

        addrport = options.get("addrport")

        if addrport:
            if ":" in addrport:
                host, port = addrport.rsplit(":", 1)

                if host == "0.0.0.0":
                    host = "127.0.0.1"
            else:
                host = "127.0.0.1"
                port = addrport
        else:
            host = "127.0.0.1"
            port = "8000"

        print(f"Starting server on {host}:{port}")

        site = Site.objects.get_current()
        site.domain = f"{host}:{port}"
        site.name = f"{host}:{port}"
        site.save()

        super().inner_run(*args, **options)
