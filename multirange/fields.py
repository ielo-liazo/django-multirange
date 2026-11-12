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
from typing import TYPE_CHECKING, Any, Generic, TypeVar, overload

from django.apps import apps
from django.contrib.postgres.fields.utils import AttributeSetter
from django.core import checks
from django.db import models
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

if TYPE_CHECKING:
    from typing_extensions import Self

try:
    # Django 6.0+ ships this mixin; on earlier versions we provide an
    # equivalent below so the check is consistent across supported Djangos.
    from django.contrib.postgres.utils import CheckPostgresInstalledMixin
except ImportError:  # pragma: no cover - exercised on Django < 6.0

    class CheckPostgresInstalledMixin:
        def _check_postgres_installed(self, *args):
            obj = args[0] if args else self
            if not apps.is_installed("django.contrib.postgres"):
                return [
                    checks.Error(
                        "'django.contrib.postgres' must be in INSTALLED_APPS "
                        f"in order to use {self.__class__.__name__}.",
                        obj=obj,
                        id="postgres.E005",
                    )
                ]
            return []

        def check(self, *args, **kwargs):
            errors = super().check(*args, **kwargs)
            errors.extend(self._check_postgres_installed(*args))
            return errors


__all__ = [
    "MultiRangeField",
    "MultiIntegerRangeField",
    "MultiBigIntegerRangeField",
    "MultiDecimalRangeField",
    "MultiDateRangeField",
    "MultiDateTimeRangeField",
    "MultiRangeOperators",
]


# Django base field class -> (PostgreSQL type, psycopg Multirange subclass).
# Looked up along the base field's MRO, so subclasses resolve to their
# nearest supported ancestor: ``SmallIntegerField`` maps to int4, and
# ``DateTimeField`` (a ``DateField`` subclass) maps to tstz, not date.
_MULTIRANGE_TYPES: dict[type[models.Field], tuple[str, type[Multirange]]] = {
    models.IntegerField: ("int4multirange", Int4Multirange),
    models.BigIntegerField: ("int8multirange", Int8Multirange),
    models.DecimalField: ("nummultirange", NumericMultirange),
    models.DateField: ("datemultirange", DateMultirange),
    models.DateTimeField: ("tstzmultirange", TimestamptzMultirange),
}


def _resolve_multirange_type(base_field: models.Field) -> tuple[str, type[Multirange]] | None:
    for cls in type(base_field).__mro__:
        if cls in _MULTIRANGE_TYPES:
            return _MULTIRANGE_TYPES[cls]
    return None


_MR = TypeVar("_MR", bound="Multirange[Any]")


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
                raise ValueError("Range tuple must have 2 or 3 elements (lower, upper[, bounds])")
        else:
            raise TypeError(f"Cannot interpret {item!r} as a Range for {multirange_type.__name__}")
    return multirange_type(ranges)


class MultiRangeField(CheckPostgresInstalledMixin, models.Field, Generic[_MR]):
    """PostgreSQL multirange field.

    Use it directly with the element type as ``base_field``, like
    ``ArrayField``::

        slots = MultiRangeField(base_field=models.DateField())

    or through one of the named subclasses (``MultiDateRangeField`` …),
    which fix ``base_field`` at class level. The PostgreSQL type and the
    psycopg ``Multirange`` subclass are derived from the base field.

    The type parameter is the Python value type, so type checkers see
    ``obj.slots`` as ``DateMultirange`` rather than ``Any``.
    """

    empty_strings_allowed = False
    description = "PostgreSQL multirange field"

    base_field: Any = None
    multirange_type: type[Multirange] = Multirange

    if TYPE_CHECKING:
        # The django-stubs mypy plugin reads these two attributes.
        _pyi_private_set_type: Any
        _pyi_private_get_type: _MR

        # Pyright (and mypy without the plugin) use the descriptor
        # signature to type attribute access on model instances.
        @overload
        def __get__(self, instance: None, owner: Any) -> Self: ...
        @overload
        def __get__(self, instance: models.Model, owner: Any) -> _MR: ...
        def __get__(self, instance: Any, owner: Any) -> Any: ...

        # Infer the value type from ``base_field``. Subclasses come
        # before their parents so the narrower match wins.
        @overload
        def __init__(
            self: MultiRangeField[TimestamptzMultirange], *args: Any, base_field: models.DateTimeField, **kwargs: Any
        ) -> None: ...
        @overload
        def __init__(
            self: MultiRangeField[DateMultirange], *args: Any, base_field: models.DateField, **kwargs: Any
        ) -> None: ...
        @overload
        def __init__(
            self: MultiRangeField[Int8Multirange], *args: Any, base_field: models.BigIntegerField, **kwargs: Any
        ) -> None: ...
        @overload
        def __init__(
            self: MultiRangeField[Int4Multirange], *args: Any, base_field: models.IntegerField, **kwargs: Any
        ) -> None: ...
        @overload
        def __init__(
            self: MultiRangeField[NumericMultirange], *args: Any, base_field: models.DecimalField, **kwargs: Any
        ) -> None: ...
        @overload
        def __init__(self, *args: Any, **kwargs: Any) -> None: ...

    def __init__(self, *args: Any, base_field: models.Field | None = None, **kwargs: Any) -> None:
        if "default_bounds" in kwargs:
            raise TypeError(f"Cannot use 'default_bounds' with {self.__class__.__name__}.")
        self._base_field_explicit = base_field is not None
        if base_field is not None:
            if self.base_field is not None:
                raise TypeError(f"{self.__class__.__name__} fixes its base field; 'base_field' cannot be passed.")
            self.base_field = base_field
            resolved = _resolve_multirange_type(base_field)
            if resolved is not None:
                self.multirange_type = resolved[1]
        elif isinstance(self.base_field, type):
            self.base_field = self.base_field()
        elif self.base_field is None:
            raise TypeError(f"{self.__class__.__name__} requires a 'base_field', e.g. base_field=models.DateField().")
        super().__init__(*args, **kwargs)

    def check(self, **kwargs: Any) -> list[checks.CheckMessage]:
        errors = super().check(**kwargs)
        if _resolve_multirange_type(self.base_field) is None:
            supported = ", ".join(cls.__name__ for cls in _MULTIRANGE_TYPES)
            errors.append(
                checks.Error(
                    f"PostgreSQL has no multirange type for {type(self.base_field).__name__}.",
                    hint=f"Use one of: {supported}.",
                    obj=self,
                    id="multirange.E001",
                )
            )
        return errors

    def db_type(self, connection):
        resolved = _resolve_multirange_type(self.base_field)
        if resolved is None:
            raise TypeError(f"PostgreSQL has no multirange type for {type(self.base_field).__name__}.")
        return resolved[0]

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        # Named subclasses fix their base field, so their migrations stay
        # exactly as before; only the generic form records it.
        if self._base_field_explicit:
            kwargs["base_field"] = self.base_field.clone()
        return name, path, args, kwargs

    @property
    def model(self):
        try:
            return self.__dict__["model"]
        except KeyError:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute 'model'")

    @model.setter
    def model(self, model):
        self.__dict__["model"] = model
        self.base_field.model = model

    @classmethod
    def _choices_is_value(cls, value):
        return isinstance(value, (list, tuple)) or super()._choices_is_value(value)

    def get_placeholder_sql(self, value, compiler, connection):
        # Django 6.1+ API. Defining it alongside get_placeholder below also
        # silences the RemovedInDjango70Warning the 6.1 shim would otherwise
        # emit for the legacy method.
        db_type = self.db_type(connection)
        if hasattr(value, "as_sql"):
            sql, params = compiler.compile(value)
            return f"{sql}::{db_type}", params
        return f"%s::{db_type}", (value,)

    def get_placeholder(self, value, compiler, connection):
        # Django < 6.1 API; removed in Django 7.0.
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
            raise ValueError("Serialized multirange must be a JSON list of range objects")
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
        """Build a form field, or ``None`` when the caller supplied no class.

        A multirange is a *set* of ranges, which has no natural single
        HTML widget, so form support is opt-in: with no ``form_class``
        this returns ``None`` and Django leaves the column out of
        generated forms.

        A ``form_class`` passed by the caller always wins. That is what
        makes ``ModelAdmin.formfield_overrides`` work — Django routes it
        through here, so ignoring the argument would leave the documented
        extension point inert.
        """
        form_class = kwargs.pop("form_class", None) or getattr(self, "form_field", None)
        if form_class is None:
            return None
        kwargs["form_class"] = form_class
        return super().formfield(**kwargs)


class MultiIntegerRangeField(MultiRangeField[Int4Multirange]):
    base_field = models.IntegerField
    multirange_type = Int4Multirange


class MultiBigIntegerRangeField(MultiRangeField[Int8Multirange]):
    base_field = models.BigIntegerField
    multirange_type = Int8Multirange


class MultiDecimalRangeField(MultiRangeField[NumericMultirange]):
    base_field = models.DecimalField
    multirange_type = NumericMultirange


class MultiDateRangeField(MultiRangeField[DateMultirange]):
    base_field = models.DateField
    multirange_type = DateMultirange


class MultiDateTimeRangeField(MultiRangeField[TimestamptzMultirange]):
    base_field = models.DateTimeField
    multirange_type = TimestamptzMultirange


# Register lookups for all multirange fields.
mr_lookups.register_for(MultiRangeField)
