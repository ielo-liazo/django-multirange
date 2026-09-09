"""Models demonstrating every django-multirange field type.

The framing is an ISP's network inventory, because that is where
multiranges earn their keep: a customer holds a *set* of non-contiguous
VLAN ranges, and you want the database — not application code — to
guarantee nobody else holds an overlapping one.

Field types covered:

===========================  ===========================  ==================
Model field                  PostgreSQL column            Django field
===========================  ===========================  ==================
``VlanReservation.vlans``    ``int4multirange``           MultiIntegerRangeField
``AsnAllocation.asns``       ``int8multirange``           MultiBigIntegerRangeField
``MaintenanceWindow.slots``  ``tstzmultirange``           MultiDateTimeRangeField
``ServiceContract.active``   ``datemultirange``           MultiDateRangeField
``ServiceContract.tiers``    ``nummultirange``            MultiDecimalRangeField
===========================  ===========================  ==================
"""

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
)


class Customer(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self) -> str:
        return self.name


class VlanReservation(models.Model):
    """VLANs held by a customer, as one set of non-contiguous ranges.

    The exclusion constraint is the headline feature: PostgreSQL renders
    it as ``EXCLUDE USING GIST (customer_id WITH =, vlans WITH &&)``, so
    two reservations for the same customer can never share a VLAN — even
    when the collision is between subranges buried in the middle of each
    multirange.

    Mixing the scalar ``customer_id WITH =`` into a GiST index requires
    the ``btree_gist`` extension; the initial migration installs it with
    ``BtreeGistExtension``.
    """

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="vlan_reservations")
    vlans = MultiIntegerRangeField()
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [
            ExclusionConstraint(
                name="vlanreservation_no_customer_overlap",
                expressions=[
                    ("customer", RangeOperators.EQUAL),
                    ("vlans", RangeOperators.OVERLAPS),
                ],
            ),
        ]

    def __str__(self) -> str:
        return f"{self.customer_id}: {self.vlans}"


class AsnAllocation(models.Model):
    """AS numbers delegated to a customer.

    32-bit ASNs overflow ``int4``, so this uses ``int8multirange``.
    """

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="asn_allocations")
    asns = MultiBigIntegerRangeField()

    class Meta:
        indexes = [GistIndex(fields=["asns"], name="asnallocation_asns_gist")]


class MaintenanceWindow(models.Model):
    """Planned downtime for a site, as a set of datetime ranges.

    A single window row can hold "Tuesday night and Thursday night",
    which is exactly the shape a multirange stores natively.
    """

    site = models.CharField(max_length=100)
    slots = MultiDateTimeRangeField()

    class Meta:
        # PostgreSQL has a default GiST operator class for every
        # multirange type, so no `opclasses` argument is needed.
        indexes = [GistIndex(fields=["slots"], name="maintenancewindow_slots_gist")]


class ServiceContract(models.Model):
    """A contract active over a set of date ranges, priced in bandwidth tiers.

    Rounds out the field types: ``datemultirange`` and ``nummultirange``.
    """

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="contracts")
    active = MultiDateRangeField(help_text="Date ranges during which the contract is live.")
    tiers = MultiDecimalRangeField(null=True, blank=True, help_text="Committed bandwidth brackets, in Gbps.")
