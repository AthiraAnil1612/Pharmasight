"""
Django management command to sync historical scan data for users
who have scan_count but no ScanHistory records
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import ScanHistory, UserProfile
from datetime import datetime, timedelta
import random


class Command(BaseCommand):
    help = 'Sync historical scan data for users who have scan_count but no ScanHistory records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Username to sync history for (default: all users with mismatched counts)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating records',
        )

    def handle(self, *args, **options):
        username = options.get('username')
        dry_run = options.get('dry_run', False)

        # List of medicines from the ML model
        medicines = [
            'Ascozin', 'Bioflu', 'Biogesic', 'Bonamine', 'Buscopan',
            'DayZinc', 'Decolgen', 'Flanax', 'Imodium', 'Lactezin',
            'Lagundi', 'Midol', 'Myra_E', 'Neurogen_E', 'Omeprazole',
            'Rinityn', 'Rogin_E', 'Sinecod', 'Tempra', 'Tuseran'
        ]

        authenticities = ['Genuine', 'Fake', 'Unknown']
        authenticity_weights = [0.7, 0.1, 0.2]  # 70% genuine, 10% fake, 20% unknown

        risk_levels = ['Low Risk', 'Medium Risk', 'High Risk', 'Unknown Risk']
        risk_weights = [0.6, 0.2, 0.1, 0.1]

        if username:
            users = User.objects.filter(username=username)
            if not users.exists():
                self.stdout.write(self.style.ERROR(f'User "{username}" not found'))
                return
        else:
            # Get all users with profiles
            users = User.objects.filter(profile__isnull=False)

        total_synced = 0

        for user in users:
            try:
                profile = UserProfile.objects.get(user=user)
            except UserProfile.DoesNotExist:
                continue

            # Check if there's a mismatch between scan_count and actual history
            actual_history_count = ScanHistory.objects.filter(user=user).count()
            scan_count = profile.scan_count

            if actual_history_count >= scan_count:
                self.stdout.write(
                    self.style.WARNING(f'User "{user.username}": Already in sync ({actual_history_count} records)')
                )
                continue

            # Calculate how many records to create
            records_to_create = scan_count - actual_history_count

            self.stdout.write(
                self.style.SUCCESS(f'User "{user.username}": Creating {records_to_create} historical records...')
            )

            if dry_run:
                self.stdout.write(f'  [DRY RUN] Would create {records_to_create} records')
                total_synced += records_to_create
                continue

            # Create historical scan records
            # Distribute them over the past 30 days
            base_date = datetime.now() - timedelta(days=30)

            for i in range(records_to_create):
                # Spread scans over time
                days_ago = random.randint(0, 30)
                hours_ago = random.randint(0, 23)
                minutes_ago = random.randint(0, 59)

                scan_date = base_date + timedelta(
                    days=days_ago,
                    hours=hours_ago,
                    minutes=minutes_ago
                )

                # Random medicine and results
                medicine = random.choice(medicines)
                authenticity = random.choices(authenticities, weights=authenticity_weights)[0]
                risk_level = random.choices(risk_levels, weights=risk_weights)[0]

                # Adjust risk based on authenticity
                if authenticity == 'Fake':
                    risk_level = 'High Risk'
                elif authenticity == 'Unknown':
                    risk_level = 'Unknown Risk'

                # Random confidence
                if authenticity == 'Genuine':
                    confidence = random.uniform(0.75, 0.99)
                elif authenticity == 'Fake':
                    confidence = random.uniform(0.80, 0.99)
                else:
                    confidence = random.uniform(0.40, 0.70)

                # Try to find a random image from media folder
                # We'll just leave image_url empty for historical records
                image_url = ''

                ScanHistory.objects.create(
                    user=user,
                    medicine_name=medicine,
                    authenticity=authenticity,
                    authenticity_confidence=confidence,
                    risk_level=risk_level,
                    scan_date=scan_date,
                    image_url=image_url
                )

                total_synced += 1

            self.stdout.write(
                self.style.SUCCESS(f'  Created {records_to_create} records for "{user.username}"')
            )

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f'\n[DRY RUN] Total records that would be created: {total_synced}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\n✓ Successfully synced {total_synced} historical scan records')
            )

