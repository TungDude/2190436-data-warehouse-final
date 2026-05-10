"""End-to-end tests for the chicago_crime bronze->silver transform."""

from __future__ import annotations

import datetime as dt
import hashlib

from decimal import Decimal

import pytest
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType,
    DecimalType,
    LongType,
    ShortType,
    StringType,
    TimestampType,
)

from glue_jobs.bronze_to_silver.sources import chicago_crime


def _bronze_root(p):
    """tests pass tmp paths as POSIX strings (Spark accepts both)."""
    return str(p / "raw")


@pytest.fixture()
def transformed(spark, isolated_bronze_root):
    return chicago_crime.transform(
        spark=spark,
        bronze_root_uri=_bronze_root(isolated_bronze_root),
    )


def test_dedup_to_four_rows(transformed):
    assert transformed.count() == 4


def test_drops_redundant_columns(transformed):
    cols = set(transformed.columns)
    assert "location" not in cols
    assert "x_coordinate" not in cols
    assert "y_coordinate" not in cols


def test_renames_year_to_source_year(transformed):
    cols = set(transformed.columns)
    assert "source_year" in cols
    assert "year" not in cols


def test_silver_schema_types(transformed):
    schema = {f.name: f.dataType for f in transformed.schema.fields}

    assert isinstance(schema["id"], LongType)
    assert isinstance(schema["case_number"], StringType)
    assert isinstance(schema["date"], TimestampType)
    assert isinstance(schema["arrest"], BooleanType)
    assert isinstance(schema["domestic"], BooleanType)
    assert isinstance(schema["ward"], ShortType)
    assert isinstance(schema["community_area"], ShortType)
    assert isinstance(schema["source_year"], ShortType)
    assert isinstance(schema["updated_on"], TimestampType)
    assert isinstance(schema["latitude"], DecimalType)
    assert schema["latitude"].precision == 9
    assert schema["latitude"].scale == 6
    assert isinstance(schema["longitude"], DecimalType)
    assert isinstance(schema["_ingest_year"], ShortType)


def test_dedup_keeps_latest_updated_on_row(transformed):
    rows = transformed.where(F.col("id") == 13000001).collect()
    assert len(rows) == 1
    only = rows[0]
    assert only.arrest is True
    assert only.updated_on == dt.datetime(2024, 6, 5, 11, 15, 0)


def test_partition_distribution_uses_occurrence_year(transformed):
    """Row 4's date is 2023-12-31 even though ingest_date is 2024-06-01;
    the partition column must follow the occurrence year."""
    counts = {
        r._ingest_year: r["count"]
        for r in transformed.groupBy("_ingest_year").count().collect()
    }
    assert counts == {2023: 1, 2024: 3}


def test_null_community_area_and_coords_survive(transformed):
    rows = transformed.where(F.col("id") == 13000002).collect()
    assert len(rows) == 1
    only = rows[0]
    assert only.community_area is None
    assert only.latitude is None
    assert only.longitude is None
    # The fixture uses CSV-escaped quotes; reader should preserve them as
    # literal quotes inside the string.
    assert '"MADISON"' in only.block


def test_decimal_precision_preserved(transformed):
    rows = transformed.where(F.col("id") == 13000004).collect()
    assert rows[0].latitude == Decimal("41.886000")
    assert rows[0].longitude == Decimal("-87.752000")


def test_idempotent_under_repeat_calls(spark, isolated_bronze_root):
    """Running the transform twice on the same input must produce the same
    set of rows (no hidden randomness, no order-dependent dedup)."""

    def fingerprint(df):
        rows = sorted(
            (
                r.id,
                r.arrest,
                r.updated_on.isoformat() if r.updated_on else None,
                int(r._ingest_year),
            )
            for r in df.select("id", "arrest", "updated_on", "_ingest_year").collect()
        )
        digest = hashlib.sha256(
            "\n".join(f"{a}|{b}|{c}|{d}" for a, b, c, d in rows).encode()
        ).hexdigest()
        return rows, digest

    first = chicago_crime.transform(
        spark=spark, bronze_root_uri=_bronze_root(isolated_bronze_root)
    )
    second = chicago_crime.transform(
        spark=spark, bronze_root_uri=_bronze_root(isolated_bronze_root)
    )
    assert fingerprint(first) == fingerprint(second)


def test_empty_bronze_returns_empty_dataframe_with_silver_schema(
    spark, empty_bronze_root
):
    df = chicago_crime.transform(
        spark=spark, bronze_root_uri=_bronze_root(empty_bronze_root)
    )
    assert df.count() == 0
    assert [f.name for f in df.schema.fields] == [
        f.name for f in chicago_crime.SILVER_SCHEMA.fields
    ]
