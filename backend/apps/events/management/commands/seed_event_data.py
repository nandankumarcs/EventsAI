from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.events.models import MovieEvent, SportEvent
from apps.events.seed_catalog import build_movie_events, build_sport_events


class Command(BaseCommand):
    help = "Seed future-only movie and sports event records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing movie and sport event records before seeding.",
        )
        parser.add_argument(
            "--skip-movies",
            action="store_true",
            help="Skip movie event seeding.",
        )
        parser.add_argument(
            "--skip-sports",
            action="store_true",
            help="Skip sport event seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        reference_date = timezone.localdate()
        self.stdout.write(
            self.style.NOTICE(f"Seeding future events using reference date {reference_date.isoformat()}"),
        )

        if options["reset"]:
            deleted_sports, _ = SportEvent.objects.all().delete()
            deleted_movies, _ = MovieEvent.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(
                    f"Deleted {deleted_movies} movie rows and {deleted_sports} sport rows before reseeding.",
                )
            )

        created_movies = 0
        created_sports = 0

        if not options["skip_movies"]:
            movie_records = build_movie_events(reference_date)
            MovieEvent.objects.bulk_create(movie_records, batch_size=500)
            created_movies = len(movie_records)

        if not options["skip_sports"]:
            sport_records = build_sport_events(reference_date)
            SportEvent.objects.bulk_create(sport_records, batch_size=500)
            created_sports = len(sport_records)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {created_movies} movie events and {created_sports} sport events.",
            )
        )
