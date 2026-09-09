"""Admin registration.

Multirange columns are editable here only because each ModelAdmin points
at a form from ``netops.forms`` that declares them explicitly. Register a
model without that and Django silently drops the multirange column from
the form — see the ``netops.forms`` module docstring.
"""

from __future__ import annotations

from django.contrib import admin

from .forms import (
    AsnAllocationForm,
    MaintenanceWindowForm,
    ServiceContractForm,
    VlanReservationForm,
)
from .models import (
    AsnAllocation,
    Customer,
    MaintenanceWindow,
    ServiceContract,
    VlanReservation,
)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(VlanReservation)
class VlanReservationAdmin(admin.ModelAdmin):
    form = VlanReservationForm
    list_display = ("customer", "vlans", "note")
    list_filter = ("customer",)


@admin.register(AsnAllocation)
class AsnAllocationAdmin(admin.ModelAdmin):
    form = AsnAllocationForm
    list_display = ("customer", "asns")


@admin.register(MaintenanceWindow)
class MaintenanceWindowAdmin(admin.ModelAdmin):
    form = MaintenanceWindowForm
    list_display = ("site", "slots")


@admin.register(ServiceContract)
class ServiceContractAdmin(admin.ModelAdmin):
    form = ServiceContractForm
    list_display = ("customer", "active", "tiers")
