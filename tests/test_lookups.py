"""ORM lookup tests for multirange fields.

These exercise the SQL operators wired up by ``multirange.lookups``:
contains/contained_by/overlap, fully_lt/gt, not_lt/gt, adjacent_to,
isempty, and the lower/upper transforms. We use deterministic data so
expectations are easy to read; property-based coverage of round-trip
behavior lives in ``test_roundtrip.py``.
"""
from __future__ import annotations

import pytest
from psycopg.types.multirange import Int4Multirange
from psycopg.types.range import Range

from .models import RangeRow


pytestmark = pytest.mark.django_db


@pytest.fixture
def rows():
    """Three rows with disjoint and overlapping multiranges."""
    a = RangeRow.objects.create(
        ints=Int4Multirange([Range(1, 5), Range(10, 20)])
    )
    b = RangeRow.objects.create(ints=Int4Multirange([Range(15, 30)]))
    c = RangeRow.objects.create(ints=Int4Multirange([Range(100, 200)]))
    return {"a": a, "b": b, "c": c}


def test_contains_scalar(rows):
    qs = RangeRow.objects.filter(ints__contains=12)
    assert set(qs.values_list("pk", flat=True)) == {rows["a"].pk}


def test_contains_scalar_no_match(rows):
    qs = RangeRow.objects.filter(ints__contains=7)
    assert list(qs) == []


def test_contains_range(rows):
    qs = RangeRow.objects.filter(ints__contains=Range(2, 4))
    assert set(qs.values_list("pk", flat=True)) == {rows["a"].pk}


def test_contains_multirange(rows):
    qs = RangeRow.objects.filter(
        ints__contains=Int4Multirange([Range(2, 4), Range(11, 19)])
    )
    assert set(qs.values_list("pk", flat=True)) == {rows["a"].pk}


def test_contained_by(rows):
    big = Int4Multirange([Range(0, 50)])
    qs = RangeRow.objects.filter(ints__contained_by=big)
    assert set(qs.values_list("pk", flat=True)) == {rows["a"].pk, rows["b"].pk}


def test_overlap(rows):
    qs = RangeRow.objects.filter(
        ints__overlap=Int4Multirange([Range(18, 25)])
    )
    assert set(qs.values_list("pk", flat=True)) == {rows["a"].pk, rows["b"].pk}


def test_fully_lt(rows):
    qs = RangeRow.objects.filter(
        ints__fully_lt=Int4Multirange([Range(50, 60)])
    )
    assert set(qs.values_list("pk", flat=True)) == {rows["a"].pk, rows["b"].pk}


def test_fully_gt(rows):
    qs = RangeRow.objects.filter(
        ints__fully_gt=Int4Multirange([Range(50, 60)])
    )
    assert set(qs.values_list("pk", flat=True)) == {rows["c"].pk}


def test_not_lt(rows):
    """``not_lt`` (``&>``) = lhs starts at or after rhs's lower bound."""
    qs = RangeRow.objects.filter(
        ints__not_lt=Int4Multirange([Range(50, 60)])
    )
    # rows a (lower=1) and b (lower=15) start before 50; only c (lower=100) does not.
    assert set(qs.values_list("pk", flat=True)) == {rows["c"].pk}


def test_not_gt(rows):
    """``not_gt`` (``&<``) = lhs ends at or before rhs's upper bound."""
    qs = RangeRow.objects.filter(
        ints__not_gt=Int4Multirange([Range(50, 60)])
    )
    # rows a (upper=20) and b (upper=30) end before 60; c (upper=200) does not.
    assert set(qs.values_list("pk", flat=True)) == {rows["a"].pk, rows["b"].pk}


def test_adjacent_to(rows):
    qs = RangeRow.objects.filter(
        ints__adjacent_to=Int4Multirange([Range(20, 25)])
    )
    # rows["a"] ends at 20 (exclusive), rows["b"] ends at 30; only "a" is adjacent.
    assert set(qs.values_list("pk", flat=True)) == {rows["a"].pk}


def test_isempty():
    empty = RangeRow.objects.create(ints=Int4Multirange())
    nonempty = RangeRow.objects.create(ints=Int4Multirange([Range(1, 5)]))
    qs = RangeRow.objects.filter(ints__isempty=True)
    assert set(qs.values_list("pk", flat=True)) == {empty.pk}
    qs = RangeRow.objects.filter(ints__isempty=False)
    assert nonempty.pk in qs.values_list("pk", flat=True)


def test_startswith_endswith(rows):
    """``lower(multirange)`` and ``upper(multirange)`` SQL functions."""
    qs = RangeRow.objects.filter(ints__startswith=1)
    assert set(qs.values_list("pk", flat=True)) == {rows["a"].pk}
    qs = RangeRow.objects.filter(ints__endswith=200)
    assert set(qs.values_list("pk", flat=True)) == {rows["c"].pk}


def test_exact_match(rows):
    qs = RangeRow.objects.filter(
        ints=Int4Multirange([Range(15, 30)])
    )
    assert set(qs.values_list("pk", flat=True)) == {rows["b"].pk}
