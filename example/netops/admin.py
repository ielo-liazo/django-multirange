"""Admin registration.

Multirange columns have no default widget, so `MultiRangeField.formfield()`
returns ``None`` and Django leaves them out of generated forms. Naming a
``form_class`` opts back in, and ``formfield_overrides`` is the idiomatic
place to do it: one entry per field type, applied to every model this
admin site renders.

The form classes themselves live in ``netops.forms``.
"""

from __future__ import annotations

from django.contrib import admin

from multirange import (
    MultiBigIntegerRangeField,
    MultiDateRangeField,
    MultiDateTimeRangeField,
    MultiDecimalRangeField,
    MultiIntegerRangeField,
)

from .forms import (
    BigIntegerMultiRangeFormField,
    DateMultiRangeFormField,
    DateTimeMultiRangeFormField,
    DecimalMultiRangeFormField,
    IntegerMultiRangeFormField,
)
from .models import (
    AsnAllocation,
    Customer,
    MaintenanceWindow,
    ServiceContract,
    VlanReservation,
)

#: Shared by every ModelAdmin below — one form field per multirange type.
MULTIRANGE_OVERRIDES = {
    MultiIntegerRangeField: {"form_class": IntegerMultiRangeFormField},
    MultiBigIntegerRangeField: {"form_class": BigIntegerMultiRangeFormField},
    MultiDecimalRangeField: {"form_class": DecimalMultiRangeFormField},
    MultiDateRangeField: {"form_class": DateMultiRangeFormField},
    MultiDateTimeRangeField: {"form_class": DateTimeMultiRangeFormField},
}


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(VlanReservation)
class VlanReservationAdmin(admin.ModelAdmin):
    formfield_overrides = MULTIRANGE_OVERRIDES
    list_display = ("customer", "vlans", "note")
    list_filter = ("customer",)


@admin.register(AsnAllocation)
class AsnAllocationAdmin(admin.ModelAdmin):
    formfield_overrides = MULTIRANGE_OVERRIDES
    list_display = ("customer", "asns")


@admin.register(MaintenanceWindow)
class MaintenanceWindowAdmin(admin.ModelAdmin):
    formfield_overrides = MULTIRANGE_OVERRIDES
    list_display = ("site", "slots")


@admin.register(ServiceContract)
class ServiceContractAdmin(admin.ModelAdmin):
    formfield_overrides = MULTIRANGE_OVERRIDES
    list_display = ("customer", "active", "tiers")
