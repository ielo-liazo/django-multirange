"""Test models exercising every multirange field type."""
from __future__ import annotations

from django.db import models

from multirange import (
    MultiBigIntegerRangeField,
    MultiDateRangeField,
    MultiDateTimeRangeField,
    MultiDecimalRangeField,
    MultiIntegerRangeField,
)


class RangeRow(models.Model):
    ints = MultiIntegerRangeField(null=True, blank=True)
    bigints = MultiBigIntegerRangeField(null=True, blank=True)
    decimals = MultiDecimalRangeField(null=True, blank=True)
    dates = MultiDateRangeField(null=True, blank=True)
    timestamps = MultiDateTimeRangeField(null=True, blank=True)

    class Meta:
        app_label = "tests"
