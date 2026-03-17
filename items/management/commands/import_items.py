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
        
        skipped = {}
        created = 0
        listings_created = 0
        
        with open(path, 'r') as file:
            reader = csv.DictReader(file)
            
            expected_fields = {"name", "quality", "source_game"}
            
            if options["create_listing"]:
                expected_fields.update({"site", "url"})
                
            if not all(f in reader.fieldnames for f in expected_fields):
                raise CommandError("missing fieldname(s)")
            
            for position, row in enumerate(reader):
                row = {k.strip(): v.strip() for k, v in row.items() if v is not None}
                
                name = row.get("name")
                quality = row.get("quality")
                source_game = row.get("source_game")
                
                if not name :
                    skipped[str(position)] = "missing name"
                    continue
                    
                if not quality :
                    skipped[str(position)] = "missing quality"
                    continue
                
                item, item_creted = Items.objects.get_or_create(
                    name = self.normalize_name(name),
                    quality = self.normalize_name(quality),
                    source_game = source_game
                )
                
                if item_creted: created += 1
                
                if options["create_listing"]:
                    site = row.get("site")
                    url = row.get("url")
                    
                    if not site:
                        skipped[str(position)] = "missing site name"
                        continue
                        
                    if not url:
                        skipped[str(position)] = "missing item url"
                        continue
                    
                    item_listing, creted = ItemListing.objects.get_or_create(
                        item = item,
                        site = site,
                        url = url
                    )
                    listings_created += 1
                     
            print(f" created items: {created}")
            print(f"listing created {listings_created}")
            print(f"skipped values:")
            for k, v in skipped.items():
                print(f"{k}: {v}")
                    
    
    @transaction.atomic    
    def import_json(self, path: Path, options):
        created = 0
        skipped = {}
        listings_created = 0
        data: list[dict] = []
        
        with open(path, 'r') as file:
            data = json.load(file)
            
            for position, item_data in enumerate(data):
                name = item_data.get("name", "")
                quality = item_data.get("quality", "")
                source_game = item_data.get("game", "")
                
                if not name:
                    skipped[str(position)] = "name field is not provided"
                    continue
                
                if not quality :
                    skipped[str(position)] = "missing quality"
                    continue
                
                item, item_created = Items.objects.get_or_create(
                    name = self.normalize_name(name),
                    quality = self.normalize_name(quality),
                    source_game = self.normalize_name(source_game)
                )
                
                if item_created: created += 1
                
                if options["create_listing"]:
                    site = item_data.get("site")
                    url = item_data.get("url")
                    
                    if not site:
                        skipped[str(position)] = "missing site name"
                        continue
                        
                    if not url:
                        skipped[str(position)] = "missing item url"
                        continue
                    
                    item_created, create = ItemListing.objects.get_or_create(
                        item = item,
                        site = site,
                        url = url
                    )
                    
                    listings_created += 1
                
            print(f" created items: {created}")
            print(f"listing created {listings_created}")
            print(f"skipped values:")
            for k, v in skipped.items():
                print(f"{k}: {v}")
                
                
    @staticmethod
    def normalize_name(name):
        normalized_name = " ".join(name.split())
        return normalized_name
                    
            
    
