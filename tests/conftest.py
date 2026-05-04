"""Pytest configuration for django-multirange tests.

When ``DATABASE_URL`` (or the discrete ``PG*`` env vars) is provided we
assume the test runner has wired up its own PostgreSQL — this is the
mode used by CI, where a service container is already running. If no
explicit configuration is found we spin up an ephemeral PostgreSQL
container via ``testcontainers`` so that ``pytest`` works out of the
box for local development.

The container is started lazily inside Django's DB setup hook, so smoke
tests that don't touch Postgres can run even without Docker available.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


def _autodetect_docker_host() -> None:
    """Point testcontainers at Docker Desktop's socket on macOS.

    Docker Desktop ships its socket under ``~/.docker/run/docker.sock``
    rather than ``/var/run/docker.sock``. testcontainers/docker-py only
    look at ``DOCKER_HOST`` and the standard socket, so we set the env
    var when we detect a desktop install. No-op if the user has already
    configured ``DOCKER_HOST`` themselves.
    """
    if os.environ.get("DOCKER_HOST"):
        return
    candidate = Path.home() / ".docker" / "run" / "docker.sock"
    if candidate.exists():
        os.environ["DOCKER_HOST"] = f"unix://{candidate}"


def _has_explicit_database() -> bool:
    if os.environ.get("DATABASE_URL"):
        return True
    return any(
        os.environ.get(var) for var in ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER")
    )


@pytest.fixture(scope="session")
def _postgres_container(request):
    if _has_explicit_database():
        return None
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError as exc:  # pragma: no cover - dev-time helper
        raise RuntimeError(
            "No DATABASE_URL/PG* env vars are set and testcontainers is not "
            "installed. Either export DATABASE_URL or install the test "
            "extras: `uv sync --extra tests`."
        ) from exc

    _autodetect_docker_host()

    # Postgres 14 introduced multirange types. Use a recent stable image.
    pg = PostgresContainer("postgres:17-alpine")
    pg.start()
    request.addfinalizer(pg.stop)

    os.environ["PGHOST"] = pg.get_container_host_ip()
    os.environ["PGPORT"] = str(pg.get_exposed_port(5432))
    os.environ["PGUSER"] = pg.username
    os.environ["PGPASSWORD"] = pg.password
    os.environ["PGDATABASE"] = pg.dbname
    return pg


def _install_btree_gist_on_template1() -> None:
    """Install btree_gist on template1 so cloned test DBs inherit it.

    The exclusion constraint on ``VlanReservation`` mixes an integer
    column (``customer_id WITH =``) with a multirange (``vlans WITH &&``)
    inside a GiST index. The integer side needs the ``btree_gist``
    extension, which must exist before pytest-django runs schema setup.
    Putting it on ``template1`` means every newly-created database picks
    it up automatically, including the test DB Django clones.
    """
    import psycopg

    from . import settings as test_settings

    cfg = test_settings._database_from_env()
    with psycopg.connect(
        host=cfg["HOST"],
        port=cfg["PORT"],
        user=cfg["USER"],
        password=cfg["PASSWORD"],
        dbname="template1",
        autocommit=True,
    ) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")


@pytest.fixture(scope="session")
def django_db_modify_db_settings(_postgres_container):
    """Refresh DATABASES with whatever PG* env vars are in scope.

    pytest-django reads ``settings.DATABASES`` once during DB setup, so
    we patch it after the container has assigned its host/port. When the
    environment was already configured, this is a no-op. We also take
    this hook to install ``btree_gist`` on ``template1`` (see above),
    since it's the last point we run before pytest-django creates the
    test DB.
    """
    from django.conf import settings

    from . import settings as test_settings

    settings.DATABASES["default"].update(test_settings._database_from_env())
    _install_btree_gist_on_template1()
