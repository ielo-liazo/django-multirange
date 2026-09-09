"""GiST index tests for multirange columns.

PostgreSQL ships a default GiST operator class for every multirange
type, so ``GistIndex`` works on a multirange column without an explicit
``opclasses`` argument. ``RangeRow`` declares one index per supported
type; these tests assert the indexes really made it into the database
and that the operators they accelerate still return correct rows.

The SP-GiST test guards the opposite claim in the README: PostgreSQL
defines no default ``spgist`` operator class for multiranges, so such an
index cannot be created.
"""

from __future__ import annotations

import pytest
from django.contrib.postgres.indexes import SpGistIndex
from django.db import ProgrammingError, connection, transaction
from psycopg.types.multirange import Int4Multirange
from psycopg.types.range import Range

from .models import RangeRow


pytestmark = pytest.mark.django_db


EXPECTED_INDEXES = {
    "rangerow_ints_gist": "ints",
    "rangerow_bigints_gist": "bigints",
    "rangerow_decimals_gist": "decimals",
    "rangerow_dates_gist": "dates",
    "rangerow_timestamps_gist": "timestamps",
}


def _index_definitions() -> dict[str, str]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = %s",
            [RangeRow._meta.db_table],
        )
        return dict(cursor.fetchall())


@pytest.mark.parametrize(("index_name", "column"), sorted(EXPECTED_INDEXES.items()))
def test_gist_index_created_for_each_multirange_type(index_name, column):
    """Every multirange column accepts a plain GiST index."""
    definitions = _index_definitions()
    assert index_name in definitions, f"{index_name} missing from {sorted(definitions)}"
    definition = definitions[index_name].lower()
    assert "using gist" in definition
    assert f"({column})" in definition


def test_overlap_query_returns_correct_rows_with_index_present():
    """The index is transparent: `&&` still returns exactly the matching rows.

    A wrong operator class would either fail to build or silently skip
    rows once the planner chose an index scan.
    """
    hit = RangeRow.objects.create(ints=Int4Multirange([Range(1, 5), Range(10, 20)]))
    RangeRow.objects.create(ints=Int4Multirange([Range(100, 200)]))

    qs = RangeRow.objects.filter(ints__overlap=Int4Multirange([Range(12, 14)]))
    assert set(qs.values_list("pk", flat=True)) == {hit.pk}


def test_spgist_index_is_not_supported_on_multiranges():
    """PostgreSQL has no default SP-GiST operator class for multiranges.

    Documented as a caveat in the README; this test fails loudly if a
    future PostgreSQL release adds one, so the docs can be corrected.
    """
    index = SpGistIndex(fields=["ints"], name="rangerow_ints_spgist")
    with pytest.raises(ProgrammingError, match="operator class"):
        with transaction.atomic():
            with connection.schema_editor() as editor:
                editor.add_index(RangeRow, index)
