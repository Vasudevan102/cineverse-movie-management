import os
import getpass
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = "Creates or updates a production superuser for Django Admin"

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='vasudevan', help='Superuser username')
        parser.add_argument('--email', type=str, default='vasudevan@cineverse.com', help='Superuser email')
        parser.add_argument('--password', type=str, default=None, help='Superuser password')

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password'] or os.environ.get('DJANGO_SUPERUSER_PASSWORD') or os.environ.get('ADMIN_PASSWORD')

        if not password:
            try:
                password = getpass.getpass(f"Enter password for superuser '{username}': ")
                confirm = getpass.getpass("Confirm password: ")
                if password != confirm:
                    self.stderr.write(self.style.ERROR("Error: Passwords do not match."))
                    return
            except Exception:
                self.stderr.write(self.style.ERROR("Error: No password provided. Set DJANGO_SUPERUSER_PASSWORD environment variable or pass --password."))
                return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': email, 'is_staff': True, 'is_superuser': True, 'is_active': True}
        )
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()

        action = "Created new" if created else "Updated existing"
        self.stdout.write(self.style.SUCCESS(f"Successfully {action} superuser '{username}' (is_staff=True, is_superuser=True, is_active=True)."))
