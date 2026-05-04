"""Model fields for PostgreSQL multirange support.

Provides Django ORM field classes for the five built-in PostgreSQL
multirange types: int4multirange, int8multirange, nummultirange,
datemultirange, tstzmultirange.

A multirange is a (possibly empty) collection of non-contiguous ranges
of the same base type. PostgreSQL automatically normalizes multiranges
on input by merging overlapping or adjacent ranges and dropping empty
ones. The Python representation uses psycopg's ``Multirange`` subclasses
which behave like a sequence of ``Range`` objects.
"""
from __future__ import annotations

import json
from typing import Any, Iterable

from django.contrib.postgres.fields.utils import AttributeSetter
from django.contrib.postgres.utils import CheckPostgresInstalledMixin
from django.db import models
from django.db.models.functions import Cast
from psycopg.types.multirange import (
    DateMultirange,
    Int4Multirange,
    Int8Multirange,
    Multirange,
    NumericMultirange,
    TimestamptzMultirange,
)
from psycopg.types.range import Range

from . import lookups as mr_lookups

__all__ = [
    "MultiRangeField",
    "MultiIntegerRangeField",
    "MultiBigIntegerRangeField",
    "MultiDecimalRangeField",
    "MultiDateRangeField",
    "MultiDateTimeRangeField",
    "MultiRangeOperators",
]


class MultiRangeOperators:
    """PostgreSQL multirange operators.

    See https://www.postgresql.org/docs/current/functions-range.html
    """

    EQUAL = "="
    NOT_EQUAL = "<>"
    CONTAINS = "@>"
    CONTAINED_BY = "<@"
    OVERLAPS = "&&"
    FULLY_LT = "<<"
    FULLY_GT = ">>"
    NOT_LT = "&>"
    NOT_GT = "&<"
    ADJACENT_TO = "-|-"


def _coerce_to_multirange(multirange_type: type[Multirange], value: Any) -> Multirange:
    """Build a Multirange of the given type from a flexible input.

    Accepts:
      - ``Multirange`` instances (returned as-is when type matches, otherwise rebuilt)
      - ``Range`` instance (wrapped as a single-range multirange)
      - iterable of ``Range`` instances
      - iterable of ``(lower, upper)`` or ``(lower, upper, bounds)`` tuples
    """
    if isinstance(value, multirange_type):
        return value
    if isinstance(value, Multirange):
        return multirange_type(list(value))
    if isinstance(value, Range):
        return multirange_type([value])
    ranges: list[Range] = []
    for item in value:
        if isinstance(item, Range):
            ranges.append(item)
        elif isinstance(item, (list, tuple)):
            if len(item) == 2:
                ranges.append(Range(item[0], item[1]))
            elif len(item) == 3:
                ranges.append(Range(item[0], item[1], item[2]))
            else:
                raise ValueError(
                    "Range tuple must have 2 or 3 elements (lower, upper[, bounds])"
                )
        else:
            raise TypeError(
                f"Cannot interpret {item!r} as a Range for {multirange_type.__name__}"
            )
    return multirange_type(ranges)


class MultiRangeField(CheckPostgresInstalledMixin, models.Field):
    """Base class for PostgreSQL multirange fields.

    Subclasses must define ``base_field`` (a Django field class for the
    element type), ``multirange_type`` (a psycopg ``Multirange`` subclass),
    and ``db_type`` returning the PostgreSQL type name.
    """

    empty_strings_allowed = False
    description = "PostgreSQL multirange field"

    base_field: Any = None
    multirange_type: type[Multirange] = Multirange

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if "default_bounds" in kwargs:
            raise TypeError(
                f"Cannot use 'default_bounds' with {self.__class__.__name__}."
            )
        if isinstance(self.base_field, type):
            self.base_field = self.base_field()
        super().__init__(*args, **kwargs)

    @property
    def model(self):
        try:
            return self.__dict__["model"]
        except KeyError:
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute 'model'"
            )

    @model.setter
    def model(self, model):
        self.__dict__["model"] = model
        self.base_field.model = model

    @classmethod
    def _choices_is_value(cls, value):
        return isinstance(value, (list, tuple)) or super()._choices_is_value(value)

    def get_placeholder(self, value, compiler, connection):
        return "%s::{}".format(self.db_type(connection))

    def get_prep_value(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, self.multirange_type):
            return value
        if isinstance(value, Multirange):
            return self.multirange_type(list(value))
        if isinstance(value, Range):
            return self.multirange_type([value])
        if isinstance(value, (list, tuple)):
            return _coerce_to_multirange(self.multirange_type, value)
        return value

    def to_python(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, self.multirange_type):
            return value
        if isinstance(value, Multirange):
            return self.multirange_type(list(value))
        if isinstance(value, str):
            data = json.loads(value)
            return self._multirange_from_serialized(data)
        if isinstance(value, (list, tuple)):
            return _coerce_to_multirange(self.multirange_type, value)
        return value

    def from_db_value(self, value, expression, connection):
        """Wrap psycopg's generic ``Multirange`` in our typed subclass.

        psycopg's multirange loaders always return the base ``Multirange``
        class regardless of the underlying PostgreSQL type. Wrapping the
        result here keeps reads symmetric with writes (which always use
        the typed subclass) and is what user code expects when checking
        ``isinstance(row.field, Int4Multirange)``.
        """
        if value is None:
            return None
        if isinstance(value, self.multirange_type):
            return value
        if isinstance(value, Multirange):
            return self.multirange_type(list(value))
        return value

    def _multirange_from_serialized(self, data: Any) -> Multirange:
        """Rebuild a multirange from the structure produced by value_to_string."""
        if not isinstance(data, list):
            raise ValueError(
                "Serialized multirange must be a JSON list of range objects"
            )
        ranges: list[Range] = []
        for item in data:
            if not isinstance(item, dict):
                raise ValueError("Each serialized range must be a JSON object")
            if item.get("empty"):
                ranges.append(Range(empty=True))
                continue
            kwargs: dict[str, Any] = {}
            for end in ("lower", "upper"):
                if end in item and item[end] is not None:
                    kwargs[end] = self.base_field.to_python(item[end])
                elif end in item:
                    kwargs[end] = None
            if "bounds" in item:
                kwargs["bounds"] = item["bounds"]
            ranges.append(Range(**kwargs))
        return self.multirange_type(ranges)

    def set_attributes_from_name(self, name: str) -> None:
        super().set_attributes_from_name(name)
        self.base_field.set_attributes_from_name(name)

    def value_to_string(self, obj: Any) -> str | None:
        value = self.value_from_object(obj)
        if value is None:
            return None
        result: list[dict[str, Any]] = []
        base_field = self.base_field
        for r in value:
            if r.isempty:
                result.append({"empty": True})
                continue
            entry: dict[str, Any] = {"bounds": r._bounds}
            for end in ("lower", "upper"):
                v = getattr(r, end)
                if v is None:
                    entry[end] = None
                else:
                    holder = AttributeSetter(base_field.attname, v)
                    entry[end] = base_field.value_to_string(holder)
            result.append(entry)
        return json.dumps(result)

    def formfield(self, **kwargs: Any) -> Any:
        # Provide a basic form field if a class is defined; otherwise return None
        # so admin/Form usage is opt-in for multiranges.
        form_class = getattr(self, "form_field", None)
        if form_class is None:
            return None
        kwargs.setdefault("form_class", form_class)
        return super().formfield(**kwargs)


class MultiIntegerRangeField(MultiRangeField):
    base_field = models.IntegerField
    multirange_type = Int4Multirange

    def db_type(self, connection):
        return "int4multirange"


class MultiBigIntegerRangeField(MultiRangeField):
    base_field = models.BigIntegerField
    multirange_type = Int8Multirange

    def db_type(self, connection):
        return "int8multirange"


class MultiDecimalRangeField(MultiRangeField):
    base_field = models.DecimalField
    multirange_type = NumericMultirange

    def db_type(self, connection):
        return "nummultirange"


class MultiDateRangeField(MultiRangeField):
    base_field = models.DateField
    multirange_type = DateMultirange

    def db_type(self, connection):
        return "datemultirange"


class MultiDateTimeRangeField(MultiRangeField):
    base_field = models.DateTimeField
    multirange_type = TimestamptzMultirange

    def db_type(self, connection):
        return "tstzmultirange"


# Register lookups for all multirange fields.
mr_lookups.register_for(MultiRangeField)
