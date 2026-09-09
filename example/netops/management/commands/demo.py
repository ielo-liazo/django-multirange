"""A guided tour of django-multirange, runnable against a real database.

    python manage.py demo

Every section below prints the query it runs and the rows that came
back, so the output doubles as documentation you can trust: if a
behaviour ever changes, this command shows it.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.core import serializers
from django.core.management.base import BaseCommand
from django.db import IntegrityError, connection, transaction
from django.utils import timezone
from psycopg.types.multirange import DateMultirange, Int4Multirange, TimestamptzMultirange
from psycopg.types.range import Range

from netops.models import (
    AsnAllocation,
    Customer,
    MaintenanceWindow,
    ServiceContract,
    VlanReservation,
)


class Command(BaseCommand):
    help = "Walk through the features of django-multirange against the demo database."

    def handle(self, *args, **options):
        self._reset()
        customers = self._seed()
        self._section_assignment()
        self._section_normalization()
        self._section_lookups()
        self._section_exclusion_constraint(customers)
        self._section_indexes()
        self._section_serialization()
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Done. Every section above ran against PostgreSQL."))

    # -- helpers ----------------------------------------------------------

    def _title(self, text: str) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(f"── {text} "))

    def _step(self, code: str, result) -> None:
        self.stdout.write(f"  {code}")
        self.stdout.write(f"    → {result}")

    def _reset(self) -> None:
        for model in (VlanReservation, AsnAllocation, MaintenanceWindow, ServiceContract, Customer):
            model.objects.all().delete()

    def _seed(self) -> dict[str, Customer]:
        return {name: Customer.objects.create(name=name) for name in ("acme", "globex", "initech")}

    # -- sections ---------------------------------------------------------

    def _section_assignment(self) -> None:
        self._title("Assigning values: tuples, Range objects, Multirange objects")
        self.stdout.write("  (every value below is the one read back from PostgreSQL)")

        acme = Customer.objects.get(name="acme")

        # A list of plain tuples is the most convenient form; the field
        # converts each one to a Range with the PostgreSQL default '[)' bounds.
        r1 = VlanReservation.objects.create(customer=acme, vlans=[(100, 110), (900, 910)], note="tuples")
        r1.refresh_from_db()
        self._step("vlans=[(100, 110), (900, 910)]", r1.vlans)

        # A 3-tuple names the bounds explicitly.
        r2 = VlanReservation.objects.create(customer=acme, vlans=[(200, 210, "[]")], note="closed bounds")
        r2.refresh_from_db()
        self._step('vlans=[(200, 210, "[]")]  # inclusive upper', r2.vlans)

        # Or hand over psycopg objects directly.
        r3 = VlanReservation.objects.create(
            customer=acme,
            vlans=Int4Multirange([Range(300, 310), Range(320, 330)]),
            note="psycopg objects",
        )
        r3.refresh_from_db()
        self._step("vlans=Int4Multirange([Range(300, 310), Range(320, 330)])", r3.vlans)

        # Reads come back as the typed psycopg subclass, not the generic base.
        fetched = VlanReservation.objects.get(pk=r1.pk)
        self._step("type(reservation.vlans)", type(fetched.vlans).__name__)

        # Unbounded ends are supported: None means "no bound on this side".
        globex = Customer.objects.get(name="globex")
        asn = AsnAllocation.objects.create(customer=globex, asns=[(4_200_000_000, None)])
        asn.refresh_from_db()
        self._step("asns=[(4_200_000_000, None)]  # int8, unbounded above", asn.asns)

    def _section_normalization(self) -> None:
        self._title("PostgreSQL normalizes multiranges on write")

        initech = Customer.objects.get(name="initech")

        # Overlapping ranges are merged into one...
        merged = VlanReservation.objects.create(customer=initech, vlans=[(10, 20), (15, 30)])
        merged.refresh_from_db()
        self._step("[(10, 20), (15, 30)]  # overlapping", f"{merged.vlans}  ({len(merged.vlans)} range)")

        # ...as are adjacent ones, since [40,50) and [50,60) touch.
        adjacent = VlanReservation.objects.create(customer=initech, vlans=[(40, 50), (50, 60)])
        adjacent.refresh_from_db()
        self._step("[(40, 50), (50, 60)]  # adjacent", f"{adjacent.vlans}  ({len(adjacent.vlans)} range)")

        # Disjoint ranges are kept apart — this is the whole point.
        disjoint = VlanReservation.objects.create(customer=initech, vlans=[(70, 80), (500, 600)])
        disjoint.refresh_from_db()
        self._step("[(70, 80), (500, 600)]  # disjoint", f"{disjoint.vlans}  ({len(disjoint.vlans)} ranges)")

        # Empty ranges disappear entirely.
        empty = VlanReservation.objects.create(customer=initech, vlans=[])
        empty.refresh_from_db()
        self._step("vlans=[]", f"{empty.vlans}  (empty: {len(empty.vlans) == 0})")

    def _section_lookups(self) -> None:
        self._title("Lookups: every PostgreSQL multirange operator")

        def vlans_of(qs):
            return sorted(str(v) for v in qs.values_list("vlans", flat=True))

        acme = Customer.objects.get(name="acme")
        qs = VlanReservation.objects.filter(customer=acme)

        # @> with a scalar: which reservation holds VLAN 905?
        self._step("filter(vlans__contains=905)", vlans_of(qs.filter(vlans__contains=905)))

        # @> with a range: which one covers all of 300..305?
        self._step(
            "filter(vlans__contains=Range(300, 306))",
            vlans_of(qs.filter(vlans__contains=Range(300, 306))),
        )

        # @> with a whole multirange.
        self._step(
            "filter(vlans__contains=Int4Multirange([Range(301, 305), Range(321, 325)]))",
            vlans_of(qs.filter(vlans__contains=Int4Multirange([Range(301, 305), Range(321, 325)]))),
        )

        # <@ : contained by a wider multirange.
        self._step(
            "filter(vlans__contained_by=[(0, 400)])",
            vlans_of(qs.filter(vlans__contained_by=[(0, 400)])),
        )

        # && : any element in common.
        self._step("filter(vlans__overlap=[(905, 1000)])", vlans_of(qs.filter(vlans__overlap=[(905, 1000)])))

        # << and >> : strictly left / right of, no overlap at all.
        self._step("filter(vlans__fully_lt=[(500, 600)])", vlans_of(qs.filter(vlans__fully_lt=[(500, 600)])))
        self._step("filter(vlans__fully_gt=[(0, 250)])", vlans_of(qs.filter(vlans__fully_gt=[(0, 250)])))

        # &> and &< : does not extend to the left / right of.
        self._step("filter(vlans__not_lt=[(250, 260)])", vlans_of(qs.filter(vlans__not_lt=[(250, 260)])))
        self._step("filter(vlans__not_gt=[(250, 260)])", vlans_of(qs.filter(vlans__not_gt=[(250, 260)])))

        # -|- : adjacent, touching without overlapping. Careful — PostgreSQL
        # only reports adjacency for a multirange holding a *single* range;
        # {[200, 211)} is adjacent to {[211, 250)}...
        self._step("filter(vlans__adjacent_to=[(211, 250)])", vlans_of(qs.filter(vlans__adjacent_to=[(211, 250)])))
        # ...but {[100, 110), [900, 910)} is not adjacent to {[110, 150)},
        # even though its first range ends exactly where that one begins.
        self._step(
            "filter(vlans__adjacent_to=[(110, 150)])  # multi-range lhs never matches",
            vlans_of(qs.filter(vlans__adjacent_to=[(110, 150)])),
        )

        # isempty, and the lower()/upper() transforms.
        self._step(
            "filter(vlans__isempty=True).count()",
            VlanReservation.objects.filter(vlans__isempty=True).count(),
        )
        self._step("filter(vlans__startswith=100)", vlans_of(qs.filter(vlans__startswith=100)))
        self._step("filter(vlans__endswith=910)", vlans_of(qs.filter(vlans__endswith=910)))

    def _section_exclusion_constraint(self, customers: dict[str, Customer]) -> None:
        self._title("Exclusion constraint: the database refuses double-booking")

        globex = customers["globex"]
        first = VlanReservation.objects.create(customer=globex, vlans=[(1000, 1010), (2000, 2010)])
        self._step("globex reserves [(1000, 1010), (2000, 2010)]", f"ok (pk={first.pk})")

        # A different customer may hold the very same VLANs.
        other = VlanReservation.objects.create(customer=customers["initech"], vlans=[(1000, 1010)])
        self._step("initech reserves [(1000, 1010)]  # different customer", f"ok (pk={other.pk})")

        # Same customer, disjoint VLANs: fine.
        ok = VlanReservation.objects.create(customer=globex, vlans=[(3000, 3010)])
        self._step("globex reserves [(3000, 3010)]  # disjoint", f"ok (pk={ok.pk})")

        # Same customer, and one subrange collides deep inside the multirange.
        try:
            with transaction.atomic():
                VlanReservation.objects.create(customer=globex, vlans=[(5000, 5010), (2005, 2020)])
        except IntegrityError as exc:
            detail = str(exc).strip().splitlines()[0]
            self._step("globex reserves [(5000, 5010), (2005, 2020)]  # 2005..2010 taken", f"rejected: {detail}")
        else:
            raise AssertionError("the exclusion constraint should have rejected this row")

    def _section_indexes(self) -> None:
        self._title("GiST indexes on multirange columns")

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE tablename IN ('netops_vlanreservation', 'netops_maintenancewindow', 'netops_asnallocation') "
                "AND indexdef ILIKE '%gist%' ORDER BY indexname"
            )
            for name, definition in cursor.fetchall():
                self._step(name, definition)

        self.stdout.write(
            "    PostgreSQL has a default GiST operator class for every multirange\n"
            "    type, so GistIndex needs no `opclasses`. SP-GiST has none and\n"
            "    cannot index these columns."
        )

    def _section_serialization(self) -> None:
        self._title("Serialization: dumpdata / loaddata round-trip")

        now = timezone.now().replace(microsecond=0)
        window = MaintenanceWindow.objects.create(
            site="pop-lyon",
            slots=TimestamptzMultirange(
                [
                    Range(now, now + dt.timedelta(hours=4)),
                    Range(now + dt.timedelta(days=2), now + dt.timedelta(days=2, hours=4)),
                ]
            ),
        )
        ServiceContract.objects.create(
            customer=Customer.objects.get(name="acme"),
            active=DateMultirange([Range(dt.date(2026, 1, 1), dt.date(2026, 7, 1))]),
            tiers=[(Decimal("0.5"), Decimal("10.5"))],
        )

        payload = serializers.serialize("json", MaintenanceWindow.objects.all())
        self._step("serializers.serialize('json', ...)", payload)

        # Round-trip it back and confirm the value survived.
        original = window.slots
        window.delete()
        for obj in serializers.deserialize("json", payload):
            obj.save()
        restored = MaintenanceWindow.objects.get(site="pop-lyon")
        self._step("deserialize + save, value preserved", restored.slots == original)
