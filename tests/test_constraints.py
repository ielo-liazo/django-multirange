"""Exclusion-constraint tests for the customer / VLAN reservation case.

A customer can reserve disjoint VLAN ranges in one row (e.g.
``[1-10, 500-600]``) — PostgreSQL stores the multirange as-is, since
the two ranges don't overlap. What we want to forbid is the same VLAN
being reserved twice for the same customer across rows: the customer
already owns VLAN 10, so a second reservation that includes VLAN 10
must fail.

The constraint is declared on ``VlanReservation.Meta.constraints``;
the ``btree_gist`` extension it depends on is installed on ``template1``
in ``conftest.py`` so the test DB inherits it.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction
from psycopg.types.range import Range

from .models import VlanReservation


pytestmark = pytest.mark.django_db


def _vlans(*ranges):
    """Shorthand: ``_vlans((1, 11), (500, 601))`` → multirange of two ranges."""
    from psycopg.types.multirange import Int4Multirange

    return Int4Multirange([Range(lo, hi) for lo, hi in ranges])


def test_disjoint_ranges_in_one_reservation_are_kept_intact():
    """The headline use case: ``[1-10, 500-600]`` round-trips faithfully.

    The two ranges are disjoint, so PostgreSQL stores them as a
    two-element multirange without merging.
    """
    reservation = VlanReservation.objects.create(customer_id=1, vlans=_vlans((1, 11), (500, 601)))
    refetched = VlanReservation.objects.get(pk=reservation.pk)
    assert len(refetched.vlans) == 2
    assert refetched.vlans[0].lower == 1 and refetched.vlans[0].upper == 11
    assert refetched.vlans[1].lower == 500 and refetched.vlans[1].upper == 601


def test_overlapping_ranges_in_one_reservation_are_merged():
    """PostgreSQL collapses overlapping ranges within a single multirange.

    This is what makes "VLAN 10 reserved twice in the same row"
    impossible by construction — the two overlapping ranges become one.
    """
    reservation = VlanReservation.objects.create(customer_id=1, vlans=_vlans((1, 11), (5, 15)))
    refetched = VlanReservation.objects.get(pk=reservation.pk)
    assert len(refetched.vlans) == 1
    assert refetched.vlans[0].lower == 1 and refetched.vlans[0].upper == 15


def test_same_customer_overlapping_vlans_rejected():
    """A second reservation for the same customer that overlaps an existing one is rejected."""
    VlanReservation.objects.create(customer_id=1, vlans=_vlans((1, 11), (500, 601)))
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            VlanReservation.objects.create(
                customer_id=1,
                vlans=_vlans((10, 20)),  # contains VLAN 10
            )


def test_same_customer_disjoint_vlans_allowed():
    """Two reservations for the same customer over disjoint VLANs both succeed."""
    VlanReservation.objects.create(customer_id=1, vlans=_vlans((1, 11)))
    VlanReservation.objects.create(customer_id=1, vlans=_vlans((100, 200), (500, 601)))
    assert VlanReservation.objects.filter(customer_id=1).count() == 2


def test_different_customers_can_reserve_overlapping_vlans():
    """The constraint is per-customer; two customers may share VLAN numbers."""
    VlanReservation.objects.create(customer_id=1, vlans=_vlans((1, 11)))
    VlanReservation.objects.create(customer_id=2, vlans=_vlans((5, 15)))
    assert VlanReservation.objects.count() == 2


def test_overlap_detected_when_only_one_subrange_collides():
    """The constraint catches conflicts even when most of the new multirange is free.

    Reserves ``[1-10, 500-600]`` for customer 1, then tries
    ``[2000-3000, 595-610]`` — the second range overlaps 595..600.
    """
    VlanReservation.objects.create(customer_id=1, vlans=_vlans((1, 11), (500, 601)))
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            VlanReservation.objects.create(customer_id=1, vlans=_vlans((2000, 3001), (595, 611)))
