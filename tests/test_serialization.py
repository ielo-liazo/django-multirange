"""Tests for value_to_string / to_python serialization round-trips.

These run without a database — we exercise the field's own serializer
the way Django's fixture loading and ``dumpdata`` use it.
"""

from __future__ import annotations

import json

import pytest
from hypothesis import given
from psycopg.types.multirange import (
    DateMultirange,
    Int4Multirange,
    Int8Multirange,
    NumericMultirange,
    TimestamptzMultirange,
)
from psycopg.types.range import Range

from multirange import (
    MultiBigIntegerRangeField,
    MultiDateRangeField,
    MultiDateTimeRangeField,
    MultiDecimalRangeField,
    MultiIntegerRangeField,
)

from . import strategies as s


class _Holder:
    """Minimal stand-in for a model instance for value_to_string."""

    def __init__(self, attname, value):
        setattr(self, attname, value)


def _serialize(field_cls, value):
    field = field_cls()
    field.set_attributes_from_name("data")
    return field.value_to_string(_Holder("data", value))


def _deserialize(field_cls, payload):
    field = field_cls()
    field.set_attributes_from_name("data")
    return field.to_python(payload)


@given(s.int4_multiranges)
def test_int4_serialize_roundtrip(value):
    payload = _serialize(MultiIntegerRangeField, value)
    assert json.loads(payload) is not None
    parsed = _deserialize(MultiIntegerRangeField, payload)
    assert isinstance(parsed, Int4Multirange)
    assert parsed == value


@given(s.int8_multiranges)
def test_int8_serialize_roundtrip(value):
    payload = _serialize(MultiBigIntegerRangeField, value)
    parsed = _deserialize(MultiBigIntegerRangeField, payload)
    assert isinstance(parsed, Int8Multirange)
    assert parsed == value


@given(s.numeric_multiranges)
def test_numeric_serialize_roundtrip(value):
    payload = _serialize(MultiDecimalRangeField, value)
    parsed = _deserialize(MultiDecimalRangeField, payload)
    assert isinstance(parsed, NumericMultirange)
    assert parsed == value


@given(s.date_multiranges)
def test_date_serialize_roundtrip(value):
    payload = _serialize(MultiDateRangeField, value)
    parsed = _deserialize(MultiDateRangeField, payload)
    assert isinstance(parsed, DateMultirange)
    assert parsed == value


@given(s.datetime_multiranges)
def test_datetime_serialize_roundtrip(value):
    payload = _serialize(MultiDateTimeRangeField, value)
    parsed = _deserialize(MultiDateTimeRangeField, payload)
    assert isinstance(parsed, TimestamptzMultirange)
    assert parsed == value


def test_serialize_none():
    assert _serialize(MultiIntegerRangeField, None) is None


def test_serialize_empty_multirange():
    payload = _serialize(MultiIntegerRangeField, Int4Multirange())
    assert json.loads(payload) == []
    parsed = _deserialize(MultiIntegerRangeField, payload)
    assert parsed == Int4Multirange()


def test_serialize_with_infinite_bounds():
    value = Int4Multirange([Range(None, 5), Range(10, None)])
    payload = _serialize(MultiIntegerRangeField, value)
    parsed = _deserialize(MultiIntegerRangeField, payload)
    assert parsed == value


def test_to_python_passes_through_multirange():
    value = Int4Multirange([Range(1, 5)])
    field = MultiIntegerRangeField()
    field.set_attributes_from_name("data")
    assert field.to_python(value) is value


def test_to_python_rejects_garbage():
    field = MultiIntegerRangeField()
    field.set_attributes_from_name("data")
    with pytest.raises(json.JSONDecodeError):
        field.to_python("not-json")
