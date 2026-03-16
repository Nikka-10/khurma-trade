from django.core.management.base import BaseCommand, CommandError
from items.models import Items, ItemListing
from django.db import transaction
from pathlib import Path
import json
import csv



class Command(BaseCommand):
    help = "Import items from CSV or JSON file into Items and optionally ItemListing"
    
    def add_arguments(self, parser):
        parser.add_argument(
            "file",
            type=str,
            help="path to the csv or json file"
        )
        parser.add_argument(
            "--create-listing",
            action="store_true",
            help="also creates ItemListing"
        )
        parser.add_argument(
            "--default-site",
            type=str,
            default="steam",
            help="default site name for ItemListing"
        )
        

    def handle(self, *args, **options):
        file_path = Path(options['file']).resolve()
        
        if not file_path:
            raise CommandError("file is not found")
        
        sfx = file_path.suffix.lower()
        
        if sfx == ".csv":
            self.import_csv(file_path, options)
        elif sfx == ".json":
            self.import_json(file_path, options)
        else:
            raise CommandError("incorrect file type, supported types: csv, json")
        
        
    @transaction.atomic
    def import_csv(self, path: Path, options):
        
        skiped = {}
        crated = 0
        
        with open(path, 'r') as file:
            reader = csv.DictReader(file)
            
            expected_fields = {"name", "quality", "source_game"}
            
            #if options["--create-listing"]:
                #    expected_fields.update({"site, url"})
                
            if not all(f in reader.fieldnames for f in expected_fields):
                raise CommandError("missing fieldname(s)")
            
            for postition, row in enumerate(reader):
                row = {k.strip(): v.strip() for k, v in row.items() if v is not None}
                
                name = row.get("name")
                quality = row.get("quality")
                
                if not name :
                    skiped[postition] = skiped["missing name"]
                    continue
                    
                if not quality :
                    skiped[postition] = skiped["missing quality"]
                    continue
                
                item, item_creted = Items.objects.get_or_create(
                    name = name,
                    quality = quality,
                )
                
                if item_creted:
                    crated += 1 
                
                print(f" created items: {crated}\n")
                print(f"skipped values:")
                for k, v in skiped:
                    print(f"{k}: {v}")
                        
    
    @transaction.atomic    
    def import_json(self, path: Path, options):
        ...
            
    
