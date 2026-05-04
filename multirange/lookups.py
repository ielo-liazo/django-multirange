"""Custom lookups and transforms for multirange fields.

PostgreSQL supports the same set of operators on multiranges as on
ranges, with the additional twist that the ``@>`` (contains) and ``<@``
(contained_by) operators accept either a value, a range, or another
multirange on the right hand side. This module wires up the standard
PostgreSQL multirange operators as Django lookups.

See https://www.postgresql.org/docs/current/functions-range.html
"""
from __future__ import annotations

from django.contrib.postgres import lookups as pg_lookups
from django.db import models
from django.db.models.functions import Cast
from django.db.models.lookups import PostgresOperatorLookup
from psycopg.types.multirange import Multirange
from psycopg.types.range import Range


__all__ = [
    "MultirangeContains",
    "MultirangeContainedBy",
    "MultirangeOverlap",
    "FullyLessThan",
    "FullyGreaterThan",
    "NotLessThan",
    "NotGreaterThan",
    "AdjacentTo",
    "IsEmpty",
    "register_for",
]


class MultirangeContains(pg_lookups.DataContains):
    """Multirange contains lookup (``@>``).

    Accepts another multirange, a single range, or a scalar value of the
    base type. Scalar values are cast to the multirange's element type.
    """

    def get_prep_lookup(self):
        if not isinstance(self.rhs, (list, tuple, Multirange, Range)):
            return Cast(self.rhs, self.lhs.field.base_field)
        return super().get_prep_lookup()


class MultirangeContainedBy(pg_lookups.ContainedBy):
    """Multirange contained_by lookup (``<@``)."""


class MultirangeOverlap(pg_lookups.Overlap):
    """Multirange overlap lookup (``&&``)."""


class FullyLessThan(PostgresOperatorLookup):
    lookup_name = "fully_lt"
    postgres_operator = "<<"


class FullyGreaterThan(PostgresOperatorLookup):
    lookup_name = "fully_gt"
    postgres_operator = ">>"


class NotLessThan(PostgresOperatorLookup):
    """Does not extend to the left of (``&>``)."""

    lookup_name = "not_lt"
    postgres_operator = "&>"


class NotGreaterThan(PostgresOperatorLookup):
    """Does not extend to the right of (``&<``)."""

    lookup_name = "not_gt"
    postgres_operator = "&<"


class AdjacentTo(PostgresOperatorLookup):
    lookup_name = "adjacent_to"
    postgres_operator = "-|-"


class IsEmpty(models.Transform):
    """Whether the multirange is empty (no ranges, or only empty ones)."""

    lookup_name = "isempty"
    function = "isempty"
    output_field = models.BooleanField()


class LowerBound(models.Transform):
    """Lower bound of a multirange (``lower``).

    Returns the lower bound of the first range in the multirange, NULL
    when the multirange is empty.
    """

    lookup_name = "startswith"
    function = "lower"

    @property
    def output_field(self):
        return self.lhs.output_field.base_field


class UpperBound(models.Transform):
    """Upper bound of a multirange (``upper``)."""

    lookup_name = "endswith"
    function = "upper"

    @property
    def output_field(self):
        return self.lhs.output_field.base_field


def register_for(field_cls: type[models.Field]) -> None:
    """Register all multirange lookups against the given field class."""
    field_cls.register_lookup(MultirangeContains)
    field_cls.register_lookup(MultirangeContainedBy)
    field_cls.register_lookup(MultirangeOverlap)
    field_cls.register_lookup(FullyLessThan)
    field_cls.register_lookup(FullyGreaterThan)
    field_cls.register_lookup(NotLessThan)
    field_cls.register_lookup(NotGreaterThan)
    field_cls.register_lookup(AdjacentTo)
    field_cls.register_lookup(IsEmpty)
    field_cls.register_lookup(LowerBound)
    field_cls.register_lookup(UpperBound)
