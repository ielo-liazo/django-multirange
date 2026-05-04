"""Form fields for PostgreSQL multirange model fields.

Form-level multirange handling is intentionally minimal: a multirange
is conceptually a sequence of ranges, which doesn't map cleanly to a
single HTML form widget. This module exposes a base ``MultiRangeFormField``
that round-trips a JSON representation, suitable for use behind an API
or a custom widget.
"""
from __future__ import annotations

import json

from django import forms
from psycopg.types.multirange import Multirange
from psycopg.types.range import Range


class MultiRangeFormField(forms.Field):
    """Form field that accepts a JSON-encoded list of ranges.

    Example input::

        [{"lower": 1, "upper": 5, "bounds": "[)"},
         {"lower": 10, "upper": 20, "bounds": "[]"}]
    """

    multirange_type: type[Multirange] = Multirange

    def to_python(self, value):
        if value in (None, "", b""):
            return None
        if isinstance(value, Multirange):
            return value
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise forms.ValidationError(
                    f"Invalid JSON for multirange: {exc}"
                ) from exc
        if not isinstance(value, list):
            raise forms.ValidationError(
                "Multirange value must decode to a JSON list of range objects."
            )
        ranges: list[Range] = []
        for item in value:
            if isinstance(item, Range):
                ranges.append(item)
                continue
            if not isinstance(item, dict):
                raise forms.ValidationError(
                    "Each range entry must be a JSON object."
                )
            if item.get("empty"):
                ranges.append(Range(empty=True))
                continue
            ranges.append(
                Range(
                    item.get("lower"),
                    item.get("upper"),
                    item.get("bounds", "[)"),
                )
            )
        return self.multirange_type(ranges)
