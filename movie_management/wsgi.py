"""
WSGI config for movie_management project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'movie_management.settings')

application = get_wsgi_application()
app = application

# Run automated DB migrations & seeding on production serverless cold-start
try:
    from django.core.management import call_command
    from movies.models import Movie
    from booking.models import Show
    from django.utils import timezone

    call_command('migrate', interactive=False)

    today = timezone.localdate()
    future_shows_count = Show.objects.filter(is_active=True, show_date__gte=today).count()
    if Movie.objects.count() == 0 or future_shows_count < 200:
        call_command('seed_data')
except Exception as e:
    pass
