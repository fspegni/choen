from django.core.management.base import BaseCommand, CommandError
import io, csv

from engine.models import RunningInstance

class Command(BaseCommand):

    COLUMNS = [ "id", "engine_id", "label", "blockchain_configuration", "num_states", "num_transitions", "num_events" ]

    def add_arguments(self, parser):
        # Positional argument (the instance IDs you already use)
        parser.add_argument('instance_ids', nargs='+', type=int)
        
        # Optional flag
        parser.add_argument('--output', type=str, help='Output file path')
        

    def _stats_to_row(self, stats):
        row = []
        for curr in self.COLUMNS:
            row.append(stats.get(curr, None))

        return row

    def handle(self, *args, **options):

        instances = RunningInstance.objects.filter(id__in=options["instance_ids"])

        try:
            num_rows = 0
            for curr in instances:
                buffer = io.StringIO()
                wr = csv.writer(buffer, quoting=csv.QUOTE_ALL)
                row = self._stats_to_row(curr.stats)
                wr.writerow(row)
                self.stdout.write(buffer.getvalue())
                self.stdout.flush()
                num_rows = num_rows + 1
            
            print(f"Done. {num_rows} row(s) written")
        except Exception as e:
            raise CommandError(f"Failed to export data: {e}") from e
