"""Hypothesis strategies for ranges and multiranges.

These strategies generate ranges with realistic boundary combinations
(open/closed, infinite endpoints) and multiranges that contain a small
number of ranges — PostgreSQL will normalize whatever we give it on
write, but we want to exercise the diversity on the Python side.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from hypothesis import strategies as st
from psycopg.types.multirange import (
    DateMultirange,
    Int4Multirange,
    Int8Multirange,
    NumericMultirange,
    TimestamptzMultirange,
)
from psycopg.types.range import Range


_BOUNDS = st.sampled_from(["[)", "(]", "[]", "()"])


def _ordered_pair(elem):
    """Draw two distinct elements and return them sorted ascending.

    Identical endpoints with exclusive bounds collapse to an empty range
    in Postgres, which is valid but unhelpful for testing — we still
    accept them in the wider strategies, but ``_ordered_pair`` itself
    never produces them.
    """
    return st.tuples(elem, elem).map(lambda p: tuple(sorted(p))).filter(
        lambda p: p[0] != p[1]
    )


def _range_from_pair_strategy(elem, allow_infinite=True):
    """Produce a Range over ``elem``, occasionally with ±infinity bounds."""
    @st.composite
    def _range(draw):
        kind = draw(
            st.sampled_from(
                ["bounded", "lower_inf", "upper_inf", "both_inf"]
                if allow_infinite
                else ["bounded"]
            )
        )
        bounds = draw(_BOUNDS)
        if kind == "bounded":
            lo, hi = draw(_ordered_pair(elem))
            return Range(lo, hi, bounds)
        if kind == "lower_inf":
            hi = draw(elem)
            return Range(None, hi, bounds)
        if kind == "upper_inf":
            lo = draw(elem)
            return Range(lo, None, bounds)
        return Range(None, None, bounds)

    return _range()


def _multirange_strategy(multirange_cls, range_strategy, *, max_size=4):
    return st.lists(range_strategy, min_size=0, max_size=max_size).map(multirange_cls)


# ---- element strategies -----------------------------------------------------

# Postgres int4: -2147483648..2147483647. Use a tighter range to keep tests fast.
int4_elements = st.integers(min_value=-(2**30), max_value=2**30)
int8_elements = st.integers(min_value=-(2**62), max_value=2**62)


# numeric: keep precision modest so JSON round-trips don't lose information.
numeric_elements = st.decimals(
    min_value=Decimal("-1e6"),
    max_value=Decimal("1e6"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

date_elements = st.dates(
    min_value=datetime.date(1970, 1, 1),
    max_value=datetime.date(2100, 1, 1),
)

# Datetime range elements: timezone-aware, second resolution. Postgres
# tstzrange has microsecond resolution but truncating to seconds avoids
# precision drift around DST/leap-second corners during round-trips.
datetime_elements = st.datetimes(
    min_value=datetime.datetime(1970, 1, 1),
    max_value=datetime.datetime(2100, 1, 1),
    timezones=st.just(datetime.timezone.utc),
).map(lambda dt: dt.replace(microsecond=0))


# ---- range strategies -------------------------------------------------------

int4_ranges = _range_from_pair_strategy(int4_elements)
int8_ranges = _range_from_pair_strategy(int8_elements)
numeric_ranges = _range_from_pair_strategy(numeric_elements)
date_ranges = _range_from_pair_strategy(date_elements)
datetime_ranges = _range_from_pair_strategy(datetime_elements)


# ---- multirange strategies --------------------------------------------------

int4_multiranges = _multirange_strategy(Int4Multirange, int4_ranges)
int8_multiranges = _multirange_strategy(Int8Multirange, int8_ranges)
numeric_multiranges = _multirange_strategy(NumericMultirange, numeric_ranges)
date_multiranges = _multirange_strategy(DateMultirange, date_ranges)
datetime_multiranges = _multirange_strategy(TimestamptzMultirange, datetime_ranges)
