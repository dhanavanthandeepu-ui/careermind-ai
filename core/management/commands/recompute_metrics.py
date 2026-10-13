from django.core.management.base import BaseCommand

from core.metrics import sync_profile_metrics
from core.models import Profile


class Command(BaseCommand):
    help = "Recompute derived student metrics (resume score, readiness, skill counts) from real resume data."

    def handle(self, *args, **options):
        n = 0
        for profile in Profile.objects.filter(role='student'):
            sync_profile_metrics(profile)
            n += 1
        self.stdout.write(self.style.SUCCESS(f"Recomputed metrics for {n} student(s)."))
