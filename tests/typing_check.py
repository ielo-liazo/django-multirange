"""Static typing checks, run with ``pyright`` in CI; never executed.

``assert_type`` fails the type check, not the test run, when the
inferred type drifts.
"""

from __future__ import annotations

from django.db import models
from psycopg.types.multirange import (
    DateMultirange,
    Int4Multirange,
    Int8Multirange,
    NumericMultirange,
    TimestamptzMultirange,
)
from typing_extensions import assert_type

from multirange import MultiDateRangeField, MultiIntegerRangeField, MultiRangeField


class Example(models.Model):
    named_dates = MultiDateRangeField()
    named_ints = MultiIntegerRangeField()
    dates = MultiRangeField(base_field=models.DateField())
    timestamps = MultiRangeField(base_field=models.DateTimeField())
    ints = MultiRangeField(base_field=models.IntegerField())
    bigints = MultiRangeField(base_field=models.BigIntegerField())
    decimals = MultiRangeField(base_field=models.DecimalField(max_digits=10, decimal_places=2))


def check(row: Example) -> None:
    assert_type(row.named_dates, DateMultirange)
    assert_type(row.named_ints, Int4Multirange)
    assert_type(row.dates, DateMultirange)
    assert_type(row.timestamps, TimestamptzMultirange)
    assert_type(row.ints, Int4Multirange)
    assert_type(row.bigints, Int8Multirange)
    assert_type(row.decimals, NumericMultirange)
    assert_type(Example.named_dates, MultiDateRangeField)
