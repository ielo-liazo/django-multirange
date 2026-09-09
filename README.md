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

### Indexes

PostgreSQL ships a default GiST operator class for multiranges, so
`django.contrib.postgres.indexes.GistIndex` works on a multirange column
with no extra configuration. This is what makes `@>`, `<@`, `&&` and the
neighbouring operators fast:

```python
from django.contrib.postgres.indexes import GistIndex


class Reservation(models.Model):
    available_seats = MultiIntegerRangeField()

    class Meta:
        indexes = [
            GistIndex(fields=["available_seats"], name="reservation_seats_gist"),
        ]
```

SP-GiST is *not* usable here: PostgreSQL defines no default `spgist`
operator class for multirange types, and creating such an index fails
with `data type int4multirange has no default operator class for access
method "spgist"`.

### Exclusion constraints

The main reason to reach for a multirange rather than several range rows
is being able to reserve a set of non-contiguous intervals as a single
value, and still have the database refuse overlaps. `ExclusionConstraint`
over the `&&` operator does exactly that:

```python
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import RangeOperators


class VlanReservation(models.Model):
    customer_id = models.IntegerField()
    vlans = MultiIntegerRangeField()

    class Meta:
        constraints = [
            ExclusionConstraint(
                name="vlanreservation_no_customer_overlap",
                expressions=[
                    ("customer_id", RangeOperators.EQUAL),
                    ("vlans", RangeOperators.OVERLAPS),
                ],
            ),
        ]
```

which PostgreSQL renders as:

```sql
EXCLUDE USING GIST (customer_id WITH =, vlans WITH &&)
```

Two reservations for the same customer can then never share a VLAN, even
when the collision is between subranges that are far apart:

```python
VlanReservation.objects.create(customer_id=1, vlans=[(100, 110), (900, 910)])
# Rejected: 905 is already taken by the row above.
VlanReservation.objects.create(customer_id=1, vlans=[(300, 310), (905, 920)])
```

Note the `customer_id WITH =` part: comparing a scalar with `=` inside a
GiST exclusion constraint requires the [`btree_gist`][btree-gist]
extension. Install it with a migration operation before the constraint is
created:

```python
from django.contrib.postgres.operations import BtreeGistExtension

class Migration(migrations.Migration):
    operations = [BtreeGistExtension(), ...]
```

A constraint on the multirange column alone (`vlans WITH &&`, no scalar
expression) needs no extension.

[btree-gist]: https://www.postgresql.org/docs/current/btree-gist.html

### Forms and the admin

A multirange is a *set* of ranges and has no natural single HTML widget,
so form support is opt-in: with no `form_class`, `formfield()` returns
`None` and Django leaves the column out of generated forms — the admin's
included. Name one and the column comes back:

```python
from multirange import MultiIntegerRangeField
from multirange.forms import MultiRangeFormField
from psycopg.types.multirange import Int4Multirange


class VlanFormField(MultiRangeFormField):
    multirange_type = Int4Multirange


class ReservationAdmin(admin.ModelAdmin):
    formfield_overrides = {
        MultiIntegerRangeField: {"form_class": VlanFormField},
    }
```

`MultiRangeFormField` parses a JSON list of range objects, e.g.
`[{"lower": 1, "upper": 5, "bounds": "[)"}]`. It leaves rendering a
stored value back to JSON, and coercing bounds to the element type, to
the application — [`example/netops/forms.py`](example/netops/forms.py)
shows both.

## Example project

[`example/`](example/) is a standalone Django project — with its own
`pyproject.toml` — exercising every feature of this package against a
real database: all five field types, the lookups, a GiST index, the
exclusion constraint, serialization, and the form/admin glue an
application has to supply.

```sh
cd example
docker compose up -d --wait
uv sync
uv run python manage.py migrate
uv run python manage.py demo
```

`manage.py demo` prints each query it runs and the rows that come back,
so the output doubles as documentation. See
[`example/README.md`](example/README.md).

## Running the tests

The suite uses `pytest`, `pytest-django`, and `hypothesis` for
property-based round-trip checks against a real PostgreSQL database.

### Local development (no manual setup)

If `DATABASE_URL` and the `PG*` environment variables are unset, the
test fixture in `tests/conftest.py` will start an ephemeral
PostgreSQL 18 container via [`testcontainers`][testcontainers] and tear
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

GitHub Actions runs `ruff check` and `ruff format --check`, then the
test suite against a `postgres:18` service container on every push and
pull request, across the matrix of supported Python (3.10–3.14) and
Django (4.2 / 5.2 / 6.0 / 6.1) versions. Each matrix cell uploads a
`coverage.xml` artifact.

## Type hints

The package is annotated and ships a `py.typed` marker, so type
checkers pick up its annotations without a stub package.

## Releasing

Releases are published to PyPI by `.github/workflows/release.yml` when a
`vX.Y.Z` tag is pushed. The workflow refuses to build if the tag does not
match `version` in `pyproject.toml`, and uploads via PyPI [Trusted
Publishing][trusted-publishing] from the `pypi` GitHub environment — no
API token is stored in the repository.

```sh
# after bumping the version in pyproject.toml and updating CHANGELOG.md
git tag v0.1.0 && git push origin v0.1.0
```

[trusted-publishing]: https://docs.pypi.org/trusted-publishers/

## License

MIT — see [LICENSE](LICENSE).
