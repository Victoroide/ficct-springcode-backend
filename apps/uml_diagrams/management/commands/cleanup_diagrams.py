"""
Management command to cleanup old anonymous diagrams.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.uml_diagrams.models import UMLDiagram


class Command(BaseCommand):
    help = 'Cleanup old anonymous UML diagrams to save storage space'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Delete diagrams older than N days (default: 30)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
    
    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        old_diagrams = UMLDiagram.objects.filter(created_at__lt=cutoff_date)
        count = old_diagrams.count()
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: Would delete {count} diagrams older than {days} days'
                )
            )
            
            if count > 0:
                self.stdout.write('Diagrams that would be deleted:')
                for diagram in old_diagrams[:10]:  # Show first 10
                    self.stdout.write(
                        f'  - {diagram.title} (created: {diagram.created_at.date()})'
                    )
                if count > 10:
                    self.stdout.write(f'  ... and {count - 10} more')
        else:
            if count == 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'No diagrams older than {days} days to delete'
                    )
                )
            else:
                old_diagrams.delete()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully deleted {count} diagrams older than {days} days'
                    )
                )

        total_diagrams = UMLDiagram.objects.count()
        today = timezone.now().date()
        diagrams_today = UMLDiagram.objects.filter(created_at__date=today).count()
        
        self.stdout.write(f'\nCurrent statistics:')
        self.stdout.write(f'  Total diagrams: {total_diagrams}')
        self.stdout.write(f'  Created today: {diagrams_today}')

        if not dry_run and count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Storage space freed up by deleting {count} old diagrams'
                )
            )
