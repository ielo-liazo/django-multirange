"""Test models exercising every multirange field type."""

from __future__ import annotations

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import RangeOperators
from django.contrib.postgres.indexes import GistIndex
from django.db import models

from multirange import (
    MultiBigIntegerRangeField,
    MultiDateRangeField,
    MultiDateTimeRangeField,
    MultiDecimalRangeField,
    MultiIntegerRangeField,
    MultiRangeField,
)


class RangeRow(models.Model):
    """One column per supported multirange type, each with a GiST index.

    PostgreSQL defines a default GiST operator class for every multirange
    type, so ``GistIndex`` needs no ``opclasses`` argument. Indexing all
    five columns keeps ``test_indexes.py`` honest about that claim for
    each field the package ships.
    """

    ints = MultiIntegerRangeField(null=True, blank=True)
    bigints = MultiBigIntegerRangeField(null=True, blank=True)
    decimals = MultiDecimalRangeField(null=True, blank=True)
    dates = MultiDateRangeField(null=True, blank=True)
    timestamps = MultiDateTimeRangeField(null=True, blank=True)

    class Meta:
        app_label = "tests"
        indexes = [
            GistIndex(fields=["ints"], name="rangerow_ints_gist"),
            GistIndex(fields=["bigints"], name="rangerow_bigints_gist"),
            GistIndex(fields=["decimals"], name="rangerow_decimals_gist"),
            GistIndex(fields=["dates"], name="rangerow_dates_gist"),
            GistIndex(fields=["timestamps"], name="rangerow_timestamps_gist"),
        ]


class GenericRow(models.Model):
    """Columns declared through the generic ``MultiRangeField(base_field=...)``."""

    dates = MultiRangeField(base_field=models.DateField(), null=True, blank=True)
    decimals = MultiRangeField(base_field=models.DecimalField(max_digits=10, decimal_places=2), null=True, blank=True)

    class Meta:
        app_label = "tests"


class VlanReservation(models.Model):
    """A customer reserves VLANs as a multirange.

    The exclusion constraint forbids any two reservations for the same
    customer from sharing a VLAN. PostgreSQL renders it as

        EXCLUDE USING GIST (customer_id WITH =, vlans WITH &&)

    which needs the ``btree_gist`` extension; that's installed on
    ``template1`` from the test conftest so every test DB inherits it.
    """

    customer_id = models.IntegerField()
    vlans = MultiIntegerRangeField()

    class Meta:
        app_label = "tests"
        constraints = [
            ExclusionConstraint(
                name="vlanreservation_no_customer_overlap",
                expressions=[
                    ("customer_id", RangeOperators.EQUAL),
                    ("vlans", RangeOperators.OVERLAPS),
                ],
            ),
        ]
