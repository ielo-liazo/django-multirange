"""Test models exercising every multirange field type."""

from __future__ import annotations

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import RangeOperators
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
