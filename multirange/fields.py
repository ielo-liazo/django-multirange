"""Model field(s) for PostgreSQL multirange support.

This file contains the `MultiRangeField` placeholder. Implement
database encoding/decoding and lookups here when ready.
"""
import json
from django.db import models
from django.contrib.postgres.utils import CheckPostgresInstalledMixin
from django.contrib.postgres.fields.utils import AttributeSetter
from django.contrib.postgres import lookups
from django.db.models.functions import Cast
from psycopg.types.multirange import Multirange, DateMultirange, NumericMultirange, Int4Multirange, Int8Multirange


__all__ = [
    "MultiRangeField",
    "MultiIntegerRangeField",
    "MultiBigIntegerRangeField",
    "MultiDecimalRangeField",
    "MultiDateTimeRangeField",
    "MultiDateRangeField",
    "MultiRangeBoundary",
    "MultiRangeOperators",
]

class MultiRangeField(CheckPostgresInstalledMixin, models.Field):
    empty_strings_allowed = False

    description = "PostgreSQL multirange field"

    def __init__(self, *args, **kwargs):
        if "default_bounds" in kwargs:
            raise TypeError(
                f"Cannot use 'default_bounds' with {self.__class__.__name__}."
            )
        # Initializing base_field here ensures that its model matches the model
        # for self.
        if hasattr(self, "base_field"):
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

    def get_prep_value(self, value):
        if value is None:
            return None
        elif isinstance(value, MultiRange):
            return value
        elif isinstance(value, (list, tuple)):
            return self.multi_range_type(value[0], value[1])
        return value

    def to_python(self, value):
        if isinstance(value, str):
            # Assume we're deserializing
            vals = json.loads(value)
            for end in ("lower", "upper"):
                if end in vals:
                    vals[end] = self.base_field.to_python(vals[end])
            value = self.multi_range_type(**vals)
        elif isinstance(value, (list, tuple)):
            value = self.multi_range_type(value[0], value[1])
        return value

    def set_attributes_from_name(self, name):
        super().set_attributes_from_name(name)
        self.base_field.set_attributes_from_name(name)

    def value_to_string(self, obj):
        value = self.value_from_object(obj)
        if value is None:
            return None
        if value.isempty:
            return json.dumps({"empty": True})
        base_field = self.base_field
        result = {"bounds": value._bounds}
        for end in ("lower", "upper"):
            val = getattr(value, end)
            if val is None:
                result[end] = None
            else:
                obj = AttributeSetter(base_field.attname, val)
                result[end] = base_field.value_to_string(obj)
        return json.dumps(result)

    def formfield(self, **kwargs):
        return None

class MultiIntegerRangeField(MultiRangeField):
    base_field = models.IntegerField
    range_type = Int4Multirange
    #form_field = forms.IntegerRangeField

    def db_type(self, connection):
        return "int4multirange"

class MultiBigIntegerRangeField(MultiRangeField):
    base_field = models.BigIntegerField
    range_type = Int8Multirange
    #form_field = forms.BigIntegerRangeField
    #
    def db_type(self, connection):
        return "int8multirange"


class MultiDecimalRangeField(MultiRangeField):
    base_field = models.DecimalField
    range_type = NumericMultirange

    def db_type(self, connection):
        return "nummultirange"

class MultiDateRangeField(MultiRangeField):
    base_field = models.DateField
    range_type = DateMultirange

    def db_type(self, connection):
        return "datemultirange"

class MultiDateTimeRangeField(MultiRangeField):
    base_field = models.DateField
    range_type = DateMultirange

    def db_type(self, connection):
        return "tstzmultirange"



class MultirangeContains(lookups.DataContains):
    def get_prep_lookup(self):
        if not isinstance(self.rhs, (list, tuple, Multirange)):
            return Cast(self.rhs, self.lhs.field.base_field)
        return super().get_prep_lookup()


MultiRangeField.register_lookup(MultirangeContains)
MultiRangeField.register_lookup(lookups.ContainedBy)
MultiRangeField.register_lookup(lookups.Overlap)
