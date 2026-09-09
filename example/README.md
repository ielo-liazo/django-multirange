# django-multirange example project

A small Django project that exercises every feature of
[`django-multirange`](../) against a real PostgreSQL database. It is a
standalone project with its own `pyproject.toml`, depending on the
library from the checkout it lives in.

The domain is an ISP's network inventory, because that is where
multiranges earn their keep: a customer holds a *set* of non-contiguous
VLAN ranges, and the database — not application code — guarantees that
nobody else holds an overlapping one.

## Running it

You need Docker (for PostgreSQL) and [uv](https://docs.astral.sh/uv/).

```sh
cd example
docker compose up -d --wait      # PostgreSQL 18 on localhost:5432
uv sync
uv run python manage.py migrate
uv run python manage.py demo
```

`demo` is the interesting part: a guided tour that prints each query it
runs and the rows that come back, section by section. To point it at
another database instead, export `DATABASE_URL`:

```sh
export DATABASE_URL=postgres://user:pass@localhost:5432/mydb
```

To browse the data in the admin:

```sh
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Tear down with `docker compose down -v`.

## What is in here

| File | What it shows |
| ---- | ------------- |
| `netops/models.py` | All five field types, a GiST index, and the exclusion constraint |
| `netops/migrations/0001_initial.py` | `BtreeGistExtension` ahead of the constraint |
| `netops/management/commands/demo.py` | Assignment, normalization, every lookup, the constraint firing, serialization |
| `netops/forms.py` | JSON form fields that make multirange columns editable |
| `netops/admin.py` | Opting into them with `formfield_overrides` |

### Field types

| Model field | PostgreSQL column | Django field |
| ----------- | ----------------- | ------------ |
| `VlanReservation.vlans` | `int4multirange` | `MultiIntegerRangeField` |
| `AsnAllocation.asns` | `int8multirange` | `MultiBigIntegerRangeField` |
| `MaintenanceWindow.slots` | `tstzmultirange` | `MultiDateTimeRangeField` |
| `ServiceContract.active` | `datemultirange` | `MultiDateRangeField` |
| `ServiceContract.tiers` | `nummultirange` | `MultiDecimalRangeField` |

### The exclusion constraint

`VlanReservation` carries the constraint that motivates the whole
package:

```sql
EXCLUDE USING gist (customer_id WITH =, vlans WITH &&)
```

Two reservations for the same customer can never share a VLAN, even when
the collision is a subrange buried in the middle of each multirange. The
`demo` command shows it accepting disjoint reservations and rejecting an
overlapping one with an `IntegrityError`.

Because the constraint mixes a scalar (`customer_id WITH =`) with a
multirange in one GiST index, it needs the `btree_gist` extension. The
initial migration installs it with `BtreeGistExtension()` before creating
the model.

## Editing multiranges in forms and the admin

Form support is opt-in. A multirange is a *set* of ranges and has no
natural single HTML widget, so `MultiRangeField.formfield()` returns
`None` unless you name a `form_class`, and Django leaves the column out
of any generated ModelForm — the admin's included. Register a model with
a bare `ModelAdmin` and the multirange column simply will not be there;
since these columns are `NOT NULL`, saving then fails.

`netops/admin.py` opts back in through `formfield_overrides`, one entry
per field type:

```python
formfield_overrides = {
    MultiIntegerRangeField: {"form_class": IntegerMultiRangeFormField},
    ...
}
```

The form fields it points at live in `netops/forms.py`. They build on
`multirange.forms.MultiRangeFormField`, which parses a JSON list of range
objects, and add the two halves the base class leaves to the caller:

* rendering a stored `Multirange` back as JSON, so an existing row loads
  into the form and can be re-submitted unchanged;
* coercing each bound through a form field for the element type, so
  `"2026-07-01"` reaches the database as a date rather than a string.

That second part is why there is one small subclass per type rather than
a single generic field.

## A PostgreSQL subtlety worth knowing

The `-|-` (adjacent) operator only reports adjacency when the left-hand
multirange holds a **single** range:

```sql
SELECT '{[100,110)}'::int4multirange           -|- '{[110,150)}'::int4multirange;  -- true
SELECT '{[100,110),[900,910)}'::int4multirange -|- '{[110,150)}'::int4multirange;  -- false
```

The `demo` command shows both cases, so the behaviour is not a surprise
the first time a query comes back empty.
