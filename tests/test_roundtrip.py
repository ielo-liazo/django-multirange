"""Property-based round-trip tests against a real PostgreSQL.

PostgreSQL normalizes multirange input on the way in: empty ranges are
dropped, adjacent and overlapping ranges are merged, and bounds on
discrete element types are canonicalized to ``[)``. Reproducing those
rules in Python would duplicate the database we are trying to test, so
instead we rely on the *idempotence* of the round-trip: once a value
has come back from the database, sending the same value back must
yield the same result. That covers every normalization pass without
us having to implement them.
"""
from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from psycopg.types.multirange import (
    DateMultirange,
    Int4Multirange,
    Int8Multirange,
    Multirange,
    NumericMultirange,
    TimestamptzMultirange,
)
from psycopg.types.range import Range

from . import strategies as s
from .models import RangeRow


pytestmark = pytest.mark.django_db


HYPO_SETTINGS = settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[
        HealthCheck.function_scoped_fixture,
        HealthCheck.too_slow,
        HealthCheck.differing_executors,
    ],
)


def _roundtrip(field_name: str, value: Multirange) -> Multirange:
    row = RangeRow.objects.create(**{field_name: value})
    return getattr(RangeRow.objects.get(pk=row.pk), field_name)


def _assert_idempotent(field_name: str, value: Multirange) -> None:
    once = _roundtrip(field_name, value)
    twice = _roundtrip(field_name, once)
    assert once == twice, (once, twice)


@HYPO_SETTINGS
@given(s.int4_multiranges)
def test_int4_roundtrip(db, value):
    once = _roundtrip("ints", value)
    assert isinstance(once, Int4Multirange)
    twice = _roundtrip("ints", once)
    assert once == twice


@HYPO_SETTINGS
@given(s.int8_multiranges)
def test_int8_roundtrip(db, value):
    once = _roundtrip("bigints", value)
    assert isinstance(once, Int8Multirange)
    twice = _roundtrip("bigints", once)
    assert once == twice


@HYPO_SETTINGS
@given(s.numeric_multiranges)
def test_numeric_roundtrip(db, value):
    once = _roundtrip("decimals", value)
    assert isinstance(once, NumericMultirange)
    twice = _roundtrip("decimals", once)
    assert once == twice


@HYPO_SETTINGS
@given(s.date_multiranges)
def test_date_roundtrip(db, value):
    once = _roundtrip("dates", value)
    assert isinstance(once, DateMultirange)
    twice = _roundtrip("dates", once)
    assert once == twice


@HYPO_SETTINGS
@given(s.datetime_multiranges)
def test_timestamptz_roundtrip(db, value):
    once = _roundtrip("timestamps", value)
    assert isinstance(once, TimestamptzMultirange)
    twice = _roundtrip("timestamps", once)
    assert once == twice


@pytest.mark.django_db
def test_null_roundtrip():
    row = RangeRow.objects.create(ints=None)
    assert RangeRow.objects.get(pk=row.pk).ints is None


@pytest.mark.django_db
def test_empty_multirange_roundtrip():
    """An empty multirange should come back as an empty multirange, not NULL."""
    row = RangeRow.objects.create(ints=Int4Multirange())
    refetched = RangeRow.objects.get(pk=row.pk).ints
    assert refetched is not None
    assert isinstance(refetched, Int4Multirange)
    assert len(refetched) == 0


@pytest.mark.django_db
def test_list_of_tuples_input():
    """The field accepts plain Python tuples and stores them correctly."""
    row = RangeRow.objects.create(ints=[(1, 5), (10, 20)])
    refetched = RangeRow.objects.get(pk=row.pk).ints
    # Ranges come back canonicalized to [) for discrete int4 type.
    assert refetched == Int4Multirange([Range(1, 5, "[)"), Range(10, 20, "[)")])
