from django.core.management.base import BaseCommand

from core.models import LearningResource

# Resources with a specific YouTube video/playlist URL I individually
# web-searched and confirmed to be a real, live, well-known freeCodeCamp
# resource at the time of writing (not a guessed/generated video ID).
VERIFIED_RESOURCES = [
    dict(skill="SQL", title="SQL Tutorial - Full Database Course for Beginners",
         youtube_url="https://www.youtube.com/playlist?list=PL13eGWMVfbjBaebtmUn-xgMXjF1blrOmP",
         level="beginner", duration="4-5 hours", order=1, resource_type="playlist",
         description="freeCodeCamp's full beginner SQL/database course."),
    dict(skill="Power BI", title="Power BI For Beginners (Full Course)",
         youtube_url="https://www.youtube.com/watch?v=sG7_ub8s_5A",
         level="beginner", duration="~3 hours", order=1, resource_type="course",
         description="End-to-end beginner walkthrough of Power BI."),
    dict(skill="Power BI", title="Data Visualization Course (freeCodeCamp, Power BI)",
         youtube_url="https://www.youtube.com/watch?v=7el3U5LbSgo",
         level="intermediate", duration="varies", order=2, resource_type="course",
         description="freeCodeCamp's Data Visualization certification content using Power BI."),
    dict(skill="Python", title="Pandas & Python for Data Analysis by Example",
         youtube_url="https://www.youtube.com/watch?v=gtjxAH8uaP0",
         level="beginner", duration="5 hours", order=1, resource_type="course",
         description="freeCodeCamp course on Python + Pandas for data analysis."),
]

# Resources where I was NOT able to individually verify a specific video
# URL within this session (no further web-search budget), so — per "do
# NOT generate fake YouTube URLs" — these point at freeCodeCamp's real,
# always-valid official channel rather than a guessed video ID. Swap
# these for a specific curated video (via Django admin) once you've
# picked and verified one.
CHANNEL_FALLBACK_URL = "https://www.youtube.com/@freecodecamp"
CHANNEL_FALLBACK_SKILLS = [
    "Excel", "Statistics", "Git", "Docker", "Kubernetes", "AWS", "Azure",
    "Terraform", "Linux", "Machine Learning", "TensorFlow", "PyTorch",
    "Django", "JavaScript", "React", "HTML", "CSS", "REST API",
    "Jenkins", "CI/CD", "Kafka",
]


class Command(BaseCommand):
    help = "Seed the LearningResource library used by the Learning Path page."

    def handle(self, *args, **options):
        created = 0
        for data in VERIFIED_RESOURCES:
            _, was_created = LearningResource.objects.get_or_create(
                skill=data["skill"], title=data["title"], defaults=data,
            )
            created += int(was_created)

        for skill in CHANNEL_FALLBACK_SKILLS:
            _, was_created = LearningResource.objects.get_or_create(
                skill=skill, title=f"{skill} tutorials on freeCodeCamp",
                defaults=dict(
                    skill=skill, title=f"{skill} tutorials on freeCodeCamp",
                    youtube_url=CHANNEL_FALLBACK_URL, level="beginner",
                    duration="varies", order=1, resource_type="course",
                    description=(
                        "Placeholder channel link (not a specific verified video) — "
                        "replace with a curated resource for this skill via Django admin."
                    ),
                ),
            )
            created += int(was_created)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {created} LearningResource rows ({len(VERIFIED_RESOURCES)} individually "
            f"verified, {len(CHANNEL_FALLBACK_SKILLS)} channel-fallback placeholders)."
        ))
