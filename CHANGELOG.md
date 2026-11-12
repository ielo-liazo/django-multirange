# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog][keepachangelog], and this
project adheres to [Semantic Versioning][semver].

[keepachangelog]: https://keepachangelog.com/en/1.1.0/
[semver]: https://semver.org/spec/v2.0.0.html

## [Unreleased]

### Added

- `MultiRangeField(base_field=...)`: declare a multirange column from its
  element field, the way `ArrayField` works. The PostgreSQL type and
  psycopg class come from the base field, and `deconstruct()` records
  `base_field` so migrations rebuild it. An unsupported base field fails
  `manage.py check` with `multirange.E001`.
- Static value typing: `MultiRangeField` is generic in its psycopg value
  type, so type checkers infer, for example, `DateMultirange` when you read
  a `MultiDateRangeField` or `MultiRangeField(base_field=models.DateField())`
  attribute.

### Changed

- The named fields are now thin subclasses of `MultiRangeField`, and
  `db_type()` is derived from the base field. Their `deconstruct()` output
  is unchanged, so existing migrations need no update.
- Instantiating `MultiRangeField()` with no `base_field` now raises
  `TypeError`. Before, it failed later, when the field was attached to a model.

## [0.1.0] - 2026-09-10

First public release. Beta: the ORM surface is exercised against every
supported Python/Django combination, but the API may still change
before 1.0.

### Added

- Model fields for the five built-in PostgreSQL multirange types:
  `MultiIntegerRangeField` (`int4multirange`), `MultiBigIntegerRangeField`
  (`int8multirange`), `MultiDecimalRangeField` (`nummultirange`),
  `MultiDateRangeField` (`datemultirange`) and `MultiDateTimeRangeField`
  (`tstzmultirange`).
- Flexible assignment: psycopg `Multirange` and `Range` instances, plus
  lists of `Range` objects or `(lower, upper[, bounds])` tuples.
- `from_db_value` returns the typed psycopg subclass matching the column
  rather than the generic `Multirange`, so reads and writes are symmetric.
- Lookups for every PostgreSQL multirange operator: `contains` (`@>`,
  accepting a multirange, a range or a scalar), `contained_by` (`<@`),
  `overlap` (`&&`), `fully_lt` (`<<`), `fully_gt` (`>>`), `not_lt` (`&>`),
  `not_gt` (`&<`), `adjacent_to` (`-|-`), plus the `isempty`, `startswith`
  (`lower()`) and `endswith` (`upper()`) transforms.
- Serialization support (`value_to_string` / `to_python`) covering empty
  ranges and unbounded ends, so `dumpdata` / `loaddata` round-trip.
- `MultiRangeFormField`, a JSON-based form field for API use. Model
  fields have no default widget, but naming a `form_class` — through
  `ModelAdmin.formfield_overrides` or a ModelForm — opts a multirange
  column back into generated forms.
- `py.typed` marker: the package ships its inline type annotations.

### Compatibility

- Python 3.10 – 3.14, Django 4.2 / 5.2 / 6.0 / 6.1, psycopg 3,
  PostgreSQL 14+ (multirange types were introduced in 14).

[Unreleased]: https://github.com/ielo-liazo/django-multirange/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ielo-liazo/django-multirange/releases/tag/v0.1.0
