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

# Run automated DB migrations, seeding & superuser auto-provisioning on production serverless cold-start
try:
    from django.core.management import call_command
    from django.contrib.auth import get_user_model
    from movies.models import Movie
    from booking.models import Show
    from django.utils import timezone

    call_command('migrate', interactive=False)

    # Auto-provision production superuser if password environment variable is set
    admin_username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'vasudevan')
    admin_email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'vasudevan@cineverse.com')
    admin_password = os.environ.get('DJANGO_SUPERUSER_PASSWORD') or os.environ.get('ADMIN_PASSWORD')

    if admin_password:
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=admin_username,
            defaults={
                'email': admin_email,
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            }
        )
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(admin_password)
        user.save()

    today = timezone.localdate()
    future_shows_count = Show.objects.filter(is_active=True, show_date__gte=today).count()
    if Movie.objects.count() == 0 or future_shows_count < 200:
        call_command('seed_data')
except Exception as e:
    pass
