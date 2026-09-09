"""Making multirange fields editable in forms and in the admin.

``django-multirange`` deliberately ships no widget: a multirange is a
*set* of ranges, which has no natural single HTML input. With no
``form_class``, ``MultiRangeField.formfield()`` returns ``None`` and
Django leaves the column out of any generated ModelForm — the admin's
included. Supplying one opts back in, which is what ``netops.admin``
does through ``formfield_overrides``.

This module holds the form fields it points at. They build on
``multirange.forms.MultiRangeFormField``, which parses a JSON list of
range objects, and add the two halves the base class leaves to the
caller:

* ``prepare_value`` — render a stored ``Multirange`` back as JSON, so an
  existing row can be loaded into the form and re-submitted unchanged.
* bound coercion — the base class stores whatever JSON contained, so
  ``"2026-07-01"`` would reach the database as a string. Each bound is
  run through a Django form field for the element type instead.
"""

from __future__ import annotations

import json
from typing import Any

from django import forms
from psycopg.types.multirange import (
    DateMultirange,
    Int4Multirange,
    Int8Multirange,
    Multirange,
    NumericMultirange,
    TimestamptzMultirange,
)
from psycopg.types.range import Range

from multirange.forms import MultiRangeFormField


def _json_default(obj: Any) -> str:
    """Serialize dates, datetimes and Decimals the way the parsers expect."""
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


class TypedMultiRangeFormField(MultiRangeFormField):
    """A JSON multirange field whose bounds are validated by element type.

    Input looks like::

        [{"lower": 100, "upper": 110, "bounds": "[)"},
         {"lower": 900, "upper": 910, "bounds": "[)"}]

    ``bounds`` is optional and defaults to ``"[)"``, matching PostgreSQL.
    """

    #: Form field used to clean each bound. Subclasses override it.
    base_form_field: forms.Field = forms.CharField(required=False)

    widget = forms.Textarea(attrs={"rows": 4, "class": "vLargeTextField"})

    def to_python(self, value):
        multirange = super().to_python(value)
        if multirange is None:
            return None
        return self.multirange_type([self._clean_range(r) for r in multirange])

    def _clean_range(self, r: Range) -> Range:
        if r.isempty:
            return r
        bounds = [None if end is None else self.base_form_field.clean(end) for end in (r.lower, r.upper)]
        return Range(bounds[0], bounds[1], r._bounds)

    def prepare_value(self, value):
        # A string means we are re-rendering input that failed validation:
        # give it back verbatim so the user does not lose their edit.
        if value is None or isinstance(value, str):
            return value
        if not isinstance(value, Multirange):
            return value
        payload = [
            {"empty": True} if r.isempty else {"lower": r.lower, "upper": r.upper, "bounds": r._bounds} for r in value
        ]
        return json.dumps(payload, default=_json_default, indent=2)


class IntegerMultiRangeFormField(TypedMultiRangeFormField):
    multirange_type = Int4Multirange
    base_form_field = forms.IntegerField(required=False)


class BigIntegerMultiRangeFormField(TypedMultiRangeFormField):
    multirange_type = Int8Multirange
    base_form_field = forms.IntegerField(required=False)


class DecimalMultiRangeFormField(TypedMultiRangeFormField):
    multirange_type = NumericMultirange
    base_form_field = forms.DecimalField(required=False)


class DateMultiRangeFormField(TypedMultiRangeFormField):
    multirange_type = DateMultirange
    base_form_field = forms.DateField(required=False)


class DateTimeMultiRangeFormField(TypedMultiRangeFormField):
    multirange_type = TimestamptzMultirange
    base_form_field = forms.DateTimeField(required=False)
