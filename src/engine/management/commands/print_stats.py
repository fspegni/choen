from django.core.management.base import BaseCommand, CommandError
import io, csv

from engine.models import RunningInstance

import json
from decimal import Decimal
from collections import OrderedDict


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

        #breakpoint()
        instances = RunningInstance.objects.filter(id__in=options["instance_ids"])

        try:
            num_files = 0
            for curr in instances:
                json_stats = curr.engine.stats
                output_path = f"{curr.label}__{curr.id}.csv"
                self.json_to_csv(json_stats, output_path)
##                buffer = io.StringIO()
##                wr = csv.writer(buffer, quoting=csv.QUOTE_ALL)
##                row = self._stats_to_row(curr.stats)
##                wr.writerow(row)
##                self.stdout.write(buffer.getvalue())
##                self.stdout.flush()
##                num_rows = num_rows + 1
                num_files += 1
            
            print(f"Done. {num_files} file(s) written")
        except Exception as e:
            raise CommandError(f"Failed to export data: {e}") from e


    def json_to_csv(self, records, output_path):
        """
        Convert records to CSV and append SUM/AVG summaries.
    
        Summaries are computed separately for:
          - deploy transactions
          - all other transaction types
    
        Args:
            records: list of dictionaries
            output_path: Destination CSV file path.
        """
    
        summary_columns = [
            "gas",
            "gas_price_actual",
            "transaction_actual_cost",
            "execution_time",
        ]
    
        # Collect all columns, preserving their original order.
        fieldnames = list(OrderedDict.fromkeys(
            key
            for record in records
            for key in record.keys()
        ))
    
        # Add a column to distinguish original and summary rows.
        fieldnames.insert(0, "row_type")
    
        # Only records with a transaction_type are actual transactions.
        transactions = [
            record for record in records
            if "transaction_type" in record
        ]
    
        summary_rows = []
    
        for group_name, group in [
            ("deploy", [
                r for r in transactions
                if r["transaction_type"] == "deploy"
            ]),
            ("non-deploy", [
                r for r in transactions
                if r["transaction_type"] != "deploy"
            ]),
        ]:
            for operation in ("SUM", "AVG"):
                row = {
                    "row_type": operation,
                    "transaction_type": group_name,
                }
    
                for column in summary_columns:
                    # Ignore missing or null values.
                    values = [
                        Decimal(str(record[column]))
                        for record in group
                        if record.get(column) is not None
                    ]
    
                    if not values:
                        row[column] = ""
                    elif operation == "SUM":
                        row[column] = format(sum(values), "f")
                    else:
                        average = sum(values) / Decimal(len(values))
                        row[column] = format(average, "f")
    
                summary_rows.append(row)
    
        # Write original records followed by the summary rows.
        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(
                csvfile,
                fieldnames=fieldnames,
                extrasaction="ignore",
            )
            writer.writeheader()
    
            for record in records:
                row = {"row_type": "DATA", **record}
                writer.writerow(row)
    
            # Optional blank line separating data from summaries.
            csvfile.write("\n")
    
            for row in summary_rows:
                writer.writerow(row)
    
        print(f"CSV generated: {output_path}")
    
