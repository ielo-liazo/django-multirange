"""Model field(s) for PostgreSQL multirange support.

This file contains the `MultiRangeField` placeholder. Implement
database encoding/decoding and lookups here when ready.
"""
from django.db import models


class MultiRangeField(models.Field):
    """Placeholder field for PostgreSQL multirange.

    Real implementations should provide `db_type`, `get_prep_value`,
    `from_db_value` and de/serialization to/from Python objects.
    """

    description = "PostgreSQL multirange field"

    def db_type(self, connection):
        # For PostgreSQL this would typically return a multirange type
        # such as 'int4multirange' or a custom type. Returning None
        # delegates type handling to Django or to custom schema operations.
        return None

    def from_db_value(self, value, expression, connection):
        return value

    def to_python(self, value):
        return value

    def get_prep_value(self, value):
        return value
