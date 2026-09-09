# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog][keepachangelog], and this
project adheres to [Semantic Versioning][semver].

[keepachangelog]: https://keepachangelog.com/en/1.1.0/
[semver]: https://semver.org/spec/v2.0.0.html

## [Unreleased]

## [0.1.0] - 2026-09-09

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
- `MultiRangeFormField`, a JSON-based form field for API use.
- `py.typed` marker: the package ships its inline type annotations.

### Compatibility

- Python 3.10 – 3.14, Django 4.2 / 5.2 / 6.0 / 6.1, psycopg 3,
  PostgreSQL 14+ (multirange types were introduced in 14).

[Unreleased]: https://github.com/ielo-liazo/django-multirange/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ielo-liazo/django-multirange/releases/tag/v0.1.0
