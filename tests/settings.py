"""Django test settings.

Database configuration is taken from the ``DATABASE_URL`` env var when
set; otherwise it falls back to discrete ``PG*`` env vars (set by the
testcontainers fixture in ``conftest.py``). Postgres 14+ is required
for native multirange support.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse


def _database_from_url(url: str) -> dict:
    parsed = urlparse(url)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": (parsed.path or "/postgres").lstrip("/") or "postgres",
        "USER": parsed.username or "postgres",
        "PASSWORD": parsed.password or "",
        "HOST": parsed.hostname or "localhost",
        "PORT": str(parsed.port or 5432),
    }


def _database_from_env() -> dict:
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("PGDATABASE", "postgres"),
        "USER": os.environ.get("PGUSER", "postgres"),
        "PASSWORD": os.environ.get("PGPASSWORD", "postgres"),
        "HOST": os.environ.get("PGHOST", "localhost"),
        "PORT": os.environ.get("PGPORT", "5432"),
    }


_url = os.environ.get("DATABASE_URL")
DATABASES = {"default": _database_from_url(_url) if _url else _database_from_env()}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "tests",
]

USE_TZ = True
TIME_ZONE = "UTC"
SECRET_KEY = "django-multirange-tests"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
