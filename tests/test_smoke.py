"""Sanity checks that don't need a database."""
from __future__ import annotations

from psycopg.types.multirange import (
    DateMultirange,
    Int4Multirange,
    Int8Multirange,
    NumericMultirange,
    TimestamptzMultirange,
)

from multirange import (
    MultiBigIntegerRangeField,
    MultiDateRangeField,
    MultiDateTimeRangeField,
    MultiDecimalRangeField,
    MultiIntegerRangeField,
    MultiRangeField,
    MultiRangeOperators,
)


def test_field_db_types():
    assert MultiIntegerRangeField().db_type(None) == "int4multirange"
    assert MultiBigIntegerRangeField().db_type(None) == "int8multirange"
    assert MultiDecimalRangeField().db_type(None) == "nummultirange"
    assert MultiDateRangeField().db_type(None) == "datemultirange"
    assert MultiDateTimeRangeField().db_type(None) == "tstzmultirange"


def test_field_multirange_types():
    assert MultiIntegerRangeField.multirange_type is Int4Multirange
    assert MultiBigIntegerRangeField.multirange_type is Int8Multirange
    assert MultiDecimalRangeField.multirange_type is NumericMultirange
    assert MultiDateRangeField.multirange_type is DateMultirange
    assert MultiDateTimeRangeField.multirange_type is TimestamptzMultirange


def test_default_bounds_rejected():
    import pytest

    with pytest.raises(TypeError):
        MultiIntegerRangeField(default_bounds="[]")


def test_operators_constants():
    assert MultiRangeOperators.CONTAINS == "@>"
    assert MultiRangeOperators.OVERLAPS == "&&"
    assert MultiRangeOperators.ADJACENT_TO == "-|-"


def test_get_prep_value_accepts_list_of_tuples():
    f = MultiIntegerRangeField()
    mr = f.get_prep_value([(1, 5), (10, 20, "[]")])
    assert isinstance(mr, Int4Multirange)
    assert len(mr) == 2
    assert mr[0].lower == 1 and mr[0].upper == 5
    assert mr[1].lower == 10 and mr[1].upper == 20
    assert mr[1]._bounds == "[]"


def test_get_prep_value_accepts_none():
    assert MultiIntegerRangeField().get_prep_value(None) is None


def test_register_lookups():
    """All multirange lookups should be registered on MultiRangeField."""
    expected = {
        "contains",
        "contained_by",
        "overlap",
        "fully_lt",
        "fully_gt",
        "not_lt",
        "not_gt",
        "adjacent_to",
        "isempty",
        "startswith",
        "endswith",
    }
    available = set(MultiRangeField.get_lookups().keys())
    assert expected.issubset(available), expected - available


def test_field_deconstruct_roundtrip():
    """Migration generation requires a working deconstruct/reconstruct cycle."""
    field = MultiIntegerRangeField(null=True, db_index=True)
    name, path, args, kwargs = field.deconstruct()
    assert path.startswith("multirange.")
    rebuilt = type(field)(*args, **kwargs)
    assert rebuilt.null is True
    assert rebuilt.db_index is True


def test_field_choices_accept_tuple_values():
    """Tuple values are valid choices for multirange fields."""
    f = MultiIntegerRangeField(
        choices=[
            ([(1, 5)], "small"),
            ([(10, 100)], "big"),
        ]
    )
    # Just verifying construction doesn't raise — Django validates that
    # _choices_is_value accepts list/tuple.
    assert f.choices is not None
