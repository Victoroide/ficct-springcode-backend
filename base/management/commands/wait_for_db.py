"""
Django management command to wait for database to be ready.
Useful for Docker containers and deployment scenarios.
"""

import time
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    """Django command to wait for database to be ready."""
    
    help = 'Wait for database to be ready'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout',
            type=int,
            default=30,
            help='Maximum time to wait for database (seconds)'
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=1,
            help='Interval between connection attempts (seconds)'
        )
    
    def handle(self, *args, **options):
        """Handle the command execution."""
        timeout = options['timeout']
        interval = options['interval']
        
        self.stdout.write('Waiting for database...')
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Check all database connections
                for db_name in connections:
                    db = connections[db_name]
                    db.cursor()
                
                self.stdout.write(
                    self.style.SUCCESS('Database is ready!')
                )
                return
                
            except OperationalError:
                self.stdout.write('Database unavailable, waiting...')
                time.sleep(interval)
        
        self.stdout.write(
            self.style.ERROR(
                f'Database not ready after {timeout} seconds'
            )
        )
        exit(1)
