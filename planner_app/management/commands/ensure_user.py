import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crea/actualiza el usuario único a partir de APP_USERNAME y APP_PASSWORD."

    def handle(self, *args, **opts):
        user, pwd = os.environ.get("APP_USERNAME", "joaquin"), os.environ.get("APP_PASSWORD")
        if not pwd:
            raise CommandError("Definí APP_PASSWORD (la app no puede quedar sin login).")
        u, created = get_user_model().objects.get_or_create(username=user, defaults={"is_staff": True, "is_superuser": True})
        u.set_password(pwd)
        u.save()
        self.stdout.write(f"Usuario '{user}' {'creado' if created else 'actualizado'}.")
