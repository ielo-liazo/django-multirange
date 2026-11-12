"""Sanity checks that don't need a database."""

from __future__ import annotations

import pytest
from django.db import models
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


def test_formfield_returns_none_without_a_form_class():
    """Form support is opt-in: a multirange has no natural single widget.

    Django reads the ``None`` as "leave this column out of the form".
    """
    assert MultiIntegerRangeField().formfield() is None


def test_formfield_honours_an_explicit_form_class():
    """An explicitly passed form_class wins over the opt-in default.

    This is the path ``ModelAdmin.formfield_overrides`` takes: Django
    merges the override into the kwargs and calls ``formfield()``. If the
    argument were ignored, that documented extension point would silently
    do nothing for multirange columns.
    """
    from multirange.forms import MultiRangeFormField

    class Int4MultiRangeFormField(MultiRangeFormField):
        multirange_type = Int4Multirange

    field = MultiIntegerRangeField(blank=True)
    form_field = field.formfield(form_class=Int4MultiRangeFormField)
    assert isinstance(form_field, Int4MultiRangeFormField)
    assert form_field.multirange_type is Int4Multirange


def test_formfield_passes_through_other_kwargs():
    """Standard formfield kwargs still reach the form field."""
    from multirange.forms import MultiRangeFormField

    field = MultiIntegerRangeField(blank=True)
    form_field = field.formfield(form_class=MultiRangeFormField, help_text="vlans", required=False)
    assert form_field.help_text == "vlans"
    assert form_field.required is False


@pytest.mark.parametrize(
    ("base_field", "db_type", "multirange_type"),
    [
        (models.IntegerField(), "int4multirange", Int4Multirange),
        (models.SmallIntegerField(), "int4multirange", Int4Multirange),
        (models.BigIntegerField(), "int8multirange", Int8Multirange),
        (models.DecimalField(max_digits=10, decimal_places=2), "nummultirange", NumericMultirange),
        (models.DateField(), "datemultirange", DateMultirange),
        (models.DateTimeField(), "tstzmultirange", TimestamptzMultirange),
    ],
)
def test_base_field_resolves_types(base_field, db_type, multirange_type):
    """The generic form derives both types from the base field's class."""
    field = MultiRangeField(base_field=base_field)
    assert field.db_type(None) == db_type
    assert field.multirange_type is multirange_type
    assert field.base_field is base_field


def test_base_field_deconstruct_roundtrip():
    field = MultiRangeField(base_field=models.DecimalField(max_digits=10, decimal_places=2), null=True)
    name, path, args, kwargs = field.deconstruct()
    assert path == "multirange.fields.MultiRangeField"
    assert isinstance(kwargs["base_field"], models.DecimalField)
    assert kwargs["base_field"] is not field.base_field
    rebuilt = MultiRangeField(*args, **kwargs)
    assert rebuilt.db_type(None) == "nummultirange"
    assert rebuilt.base_field.max_digits == 10
    assert rebuilt.null is True


def test_named_subclass_deconstruct_omits_base_field():
    """Existing migrations for the named classes must not change."""
    _, path, _, kwargs = MultiDateRangeField(null=True).deconstruct()
    assert path == "multirange.fields.MultiDateRangeField"
    assert "base_field" not in kwargs


def test_named_subclass_rejects_base_field():
    with pytest.raises(TypeError, match="fixes its base field"):
        MultiDateRangeField(base_field=models.IntegerField())


def test_missing_base_field_rejected():
    with pytest.raises(TypeError, match="requires a 'base_field'"):
        MultiRangeField()


def test_unsupported_base_field_fails_check():
    field = MultiRangeField(base_field=models.CharField(max_length=10))
    field.set_attributes_from_name("labels")
    errors = [e for e in field.check() if e.id == "multirange.E001"]
    assert len(errors) == 1
    assert "CharField" in errors[0].msg
    with pytest.raises(TypeError, match="no multirange type"):
        field.db_type(None)
