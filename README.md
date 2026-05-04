# django-multirange

Django ORM support for [PostgreSQL multirange types][pg-multirange]
(`int4multirange`, `int8multirange`, `nummultirange`, `datemultirange`,
`tstzmultirange`). Multiranges store a (possibly empty) collection of
non-contiguous ranges of the same base type — think "many ranges in
one column" — and PostgreSQL provides the same set of operators on
them as on plain ranges, plus the ability to compare a multirange
against a single range or value.

This package targets PostgreSQL 14+ (where multirange types were
introduced) and Django 4.2+ on top of `psycopg` 3.

[pg-multirange]: https://www.postgresql.org/docs/current/rangetypes.html#RANGETYPES-BUILTIN

## Installation

```sh
pip install django-multirange
```

## Usage

```python
from django.db import models
from multirange import MultiIntegerRangeField, MultiDateRangeField


class Reservation(models.Model):
    available_seats = MultiIntegerRangeField(null=True)
    blackout_dates = MultiDateRangeField(null=True)
```

Setting values:

```python
from datetime import date
from psycopg.types.multirange import Int4Multirange, DateMultirange
from psycopg.types.range import Range

Reservation.objects.create(
    available_seats=Int4Multirange([Range(1, 10), Range(20, 30)]),
    blackout_dates=DateMultirange([
        Range(date(2026, 7, 1), date(2026, 7, 15)),
    ]),
)

# Tuples and lists are accepted too — they are converted to Ranges:
Reservation.objects.create(available_seats=[(1, 10), (20, 30, "[]")])
```

### Lookups

All standard PostgreSQL multirange operators are exposed as Django
lookups:

| Lookup        | Operator | Meaning                                         |
| ------------- | -------- | ----------------------------------------------- |
| `contains`    | `@>`     | Contains another multirange / range / element   |
| `contained_by`| `<@`     | Is contained by another multirange              |
| `overlap`     | `&&`     | Has any element in common                       |
| `fully_lt`    | `<<`     | Strictly left of                                |
| `fully_gt`    | `>>`     | Strictly right of                               |
| `not_lt`      | `&>`     | Does not extend to the left of                  |
| `not_gt`      | `&<`     | Does not extend to the right of                 |
| `adjacent_to` | `-\|-`   | Adjacent to                                     |
| `isempty`     | n/a      | Multirange is empty                             |
| `startswith`  | `lower(...)` | Lower bound equals value                    |
| `endswith`    | `upper(...)` | Upper bound equals value                    |

```python
Reservation.objects.filter(available_seats__contains=5)
Reservation.objects.filter(available_seats__overlap=Int4Multirange([Range(8, 22)]))
Reservation.objects.filter(blackout_dates__isempty=False)
```

## Running the tests

The suite uses `pytest`, `pytest-django`, and `hypothesis` for
property-based round-trip checks against a real PostgreSQL database.

### Local development (no manual setup)

If `DATABASE_URL` and the `PG*` environment variables are unset, the
test fixture in `tests/conftest.py` will start an ephemeral
PostgreSQL 17 container via [`testcontainers`][testcontainers] and tear
it down at the end of the session. You only need Docker to be running:

```sh
uv sync --extra tests
uv run pytest
```

On macOS the test setup auto-detects Docker Desktop's socket at
`~/.docker/run/docker.sock`, so no `DOCKER_HOST` export is needed.

[testcontainers]: https://testcontainers-python.readthedocs.io/

### Local development (existing PostgreSQL)

If you already have a PostgreSQL 14+ instance, just point the tests at
it:

```sh
export DATABASE_URL=postgres://user:pass@localhost:5432/mydb
uv run pytest
```

Discrete `PGHOST`/`PGPORT`/`PGUSER`/`PGPASSWORD`/`PGDATABASE` env vars
are also recognised.

### Smoke tests only (no database)

Tests in `tests/test_smoke.py` and `tests/test_serialization.py` don't
need a database — useful when iterating on field code without spinning
up Postgres:

```sh
uv run pytest tests/test_smoke.py tests/test_serialization.py
```

### CI

GitHub Actions uses a `postgres:17` service container on every push
and pull request, against the matrix of supported Python (3.10–3.13)
and Django (4.2 / 5.2 / 6.0) versions.

## License

MIT — see [LICENSE](LICENSE).
