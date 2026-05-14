"""Spark-only tests for silver_to_gold/common.py helpers.

No Postgres / Docker required. Exercises the pure-DataFrame functions
that the merge SQL relies on.
"""

from __future__ import annotations

from datetime import date

import pytest
from pyspark.sql import Row
from pyspark.sql import functions as F

from glue_jobs.silver_to_gold import common


# ---------------------------------------------------------------------------
# read_silver_table — sentinel filter
# ---------------------------------------------------------------------------


def test_read_silver_table_filters_sentinel_partition(spark, monkeypatch):
    """Rows with _ingest_year=9999 must be dropped (CLAUDE.md Silver-Layer)."""
    df = spark.createDataFrame(
        [
            Row(id=1, _ingest_year=2024),
            Row(id=2, _ingest_year=2023),
            Row(id=3, _ingest_year=9999),  # sentinel
        ]
    )

    captured = {}

    def fake_table(name):
        captured["name"] = name
        return df

    monkeypatch.setattr(spark, "table", fake_table)
    out = common.read_silver_table(spark, "silver_db", "chicago_crime")
    assert captured["name"] == "silver_db.chicago_crime"
    ids = sorted(r.id for r in out.collect())
    assert ids == [1, 2]
    assert common.SENTINEL_INGEST_YEAR == 9999


def test_read_silver_table_no_ingest_year_column_passes_through(spark, monkeypatch):
    """Tables lacking _ingest_year (e.g. seed dims) must not error."""
    df = spark.createDataFrame([Row(id=1), Row(id=2)])
    monkeypatch.setattr(spark, "table", lambda _name: df)
    out = common.read_silver_table(spark, "silver_db", "plain_table")
    assert out.count() == 2


# ---------------------------------------------------------------------------
# compute_scd_hash
# ---------------------------------------------------------------------------


def test_compute_scd_hash_is_deterministic(spark):
    df = spark.createDataFrame(
        [
            Row(a="x", b="y"),
            Row(a="x", b="y"),
        ]
    )
    out = common.compute_scd_hash(df, ["a", "b"]).collect()
    assert out[0].scd_hash == out[1].scd_hash
    assert len(out[0].scd_hash) == 32  # SHA-256 raw bytes


def test_compute_scd_hash_different_values_different_hash(spark):
    df = spark.createDataFrame(
        [
            Row(a="x", b="y"),
            Row(a="x", b="z"),
        ]
    )
    out = common.compute_scd_hash(df, ["a", "b"]).collect()
    assert out[0].scd_hash != out[1].scd_hash


def test_compute_scd_hash_null_vs_empty_disambiguation(spark):
    """Critical: (NULL, 'x') and ('', 'x') must hash differently.

    The earlier design used empty string for both null replacement and
    column separator, collapsing these pairs.
    """
    df = spark.createDataFrame(
        [
            Row(a=None, b="x"),
            Row(a="", b="x"),
        ]
    )
    out = common.compute_scd_hash(df, ["a", "b"]).collect()
    assert out[0].scd_hash != out[1].scd_hash


def test_compute_scd_hash_column_boundary_disambiguation(spark):
    """('ab', 'c') and ('a', 'bc') must hash differently.

    Without a non-empty separator, the concatenated 'abc' would
    collide. The _COL_SEPARATOR sentinel breaks the collision.
    """
    df = spark.createDataFrame(
        [
            Row(a="ab", b="c"),
            Row(a="a", b="bc"),
        ]
    )
    out = common.compute_scd_hash(df, ["a", "b"]).collect()
    assert out[0].scd_hash != out[1].scd_hash


def test_compute_scd_hash_empty_tracked_cols_yields_constant(spark):
    """Empty tracked_cols collapses SCD2 to insert-once-per-NK; every row
    hashes to the same value, which is the V1 dim_location contract."""
    df = spark.createDataFrame([Row(nk="a"), Row(nk="b"), Row(nk="c")])
    out = common.compute_scd_hash(df, []).collect()
    assert out[0].scd_hash == out[1].scd_hash == out[2].scd_hash


# ---------------------------------------------------------------------------
# resolve_scd2_fk_asof
# ---------------------------------------------------------------------------


@pytest.fixture()
def dim_with_two_versions(spark):
    """A toy SCD2 dim with one NK and two effective ranges."""
    return spark.createDataFrame(
        [
            Row(
                dim_key=10,
                nk="A",
                scd_start_date=date(2020, 1, 1),
                scd_end_date=date(2022, 12, 31),
            ),
            Row(
                dim_key=11,
                nk="A",
                scd_start_date=date(2023, 1, 1),
                scd_end_date=date(9999, 12, 31),
            ),
        ]
    )


def test_resolve_scd2_fk_asof_picks_active_version(spark, dim_with_two_versions):
    fact = spark.createDataFrame(
        [
            Row(crime_id=1, nk="A", occurrence_date=date(2021, 6, 15)),
            Row(crime_id=2, nk="A", occurrence_date=date(2024, 6, 15)),
        ]
    )
    resolved = common.resolve_scd2_fk_asof(
        fact,
        dim_with_two_versions,
        natural_key=["nk"],
        event_date_col="occurrence_date",
        dim_key_col="dim_key",
    ).collect()
    by_crime = {r.crime_id: r.dim_key for r in resolved}
    assert by_crime == {1: 10, 2: 11}


def test_resolve_scd2_fk_asof_null_nk_falls_to_unknown(
    spark, dim_with_two_versions
):
    from pyspark.sql.types import DateType, IntegerType, StringType, StructField, StructType

    schema = StructType(
        [
            StructField("crime_id", IntegerType(), nullable=False),
            StructField("nk", StringType(), nullable=True),
            StructField("occurrence_date", DateType(), nullable=False),
        ]
    )
    fact = spark.createDataFrame(
        [(3, None, date(2024, 6, 15))],
        schema=schema,
    )
    resolved = common.resolve_scd2_fk_asof(
        fact,
        dim_with_two_versions,
        natural_key=["nk"],
        event_date_col="occurrence_date",
        dim_key_col="dim_key",
        unknown_key=0,
    ).collect()
    assert resolved[0].dim_key == 0


def test_resolve_scd2_fk_asof_event_before_any_version_falls_to_unknown(
    spark, dim_with_two_versions
):
    """A fact whose occurrence date predates the dim's first version
    should NOT match; it must fall to the Unknown surrogate."""
    fact = spark.createDataFrame(
        [
            Row(crime_id=4, nk="A", occurrence_date=date(2019, 6, 15)),
        ]
    )
    resolved = common.resolve_scd2_fk_asof(
        fact,
        dim_with_two_versions,
        natural_key=["nk"],
        event_date_col="occurrence_date",
        dim_key_col="dim_key",
        unknown_key=0,
    ).collect()
    assert resolved[0].dim_key == 0


# ---------------------------------------------------------------------------
# secret_to_jdbc_props — argument validation only (boto3 mocked)
# ---------------------------------------------------------------------------


def test_secret_to_jdbc_props_raises_on_missing_field(monkeypatch):
    """If the secret is missing a required field, raise with a clear message."""
    import json

    class FakeClient:
        def get_secret_value(self, SecretId):  # noqa: N803
            return {
                "SecretString": json.dumps(
                    {
                        "username": "u",
                        "password": "p",
                        # missing host/port/dbname/engine
                    }
                )
            }

    monkeypatch.setattr("boto3.client", lambda *_a, **_k: FakeClient())
    with pytest.raises(RuntimeError, match="missing required fields"):
        common.secret_to_jdbc_props(secret_arn="arn:test", region="us-east-1")


# ---------------------------------------------------------------------------
# coalesce_to_seeded_date_key — post-2030 and pre-2018 guard
# ---------------------------------------------------------------------------


def test_coalesce_to_seeded_date_key_passes_through_seeded_keys(spark):
    """Smart keys present in dim_date pass through unchanged."""
    facts = spark.createDataFrame(
        [
            Row(crime_id=1, raw_key=20240615),
            Row(crime_id=2, raw_key=20250101),
        ]
    )
    dim_keys = spark.createDataFrame(
        [Row(date_key=20240615), Row(date_key=20250101), Row(date_key=20300101)]
    )
    out = common.coalesce_to_seeded_date_key(
        facts, dim_keys, raw_col="raw_key", out_col="date_key"
    ).collect()
    by_crime = {r.crime_id: r.date_key for r in out}
    assert by_crime == {1: 20240615, 2: 20250101}


def test_coalesce_to_seeded_date_key_post_seed_range_falls_to_unknown(spark):
    """A computed YYYYMMDD outside the seeded dim_date range (e.g.
    post-2030 from an updated_on field) must fall to date_key=0 rather
    than fail the downstream FK insert. Closes silver-to-gold-plan §7's
    'dim_date range vs ETL contradiction' risk."""
    facts = spark.createDataFrame(
        [
            Row(crime_id=1, raw_key=20240615),  # seeded
            Row(crime_id=2, raw_key=20310101),  # post-seed
            Row(crime_id=3, raw_key=19900105),  # pre-seed
        ]
    )
    dim_keys = spark.createDataFrame([Row(date_key=20240615)])
    out = common.coalesce_to_seeded_date_key(
        facts, dim_keys, raw_col="raw_key", out_col="date_key"
    ).collect()
    by_crime = {r.crime_id: r.date_key for r in out}
    assert by_crime == {1: 20240615, 2: 0, 3: 0}


def test_coalesce_to_seeded_date_key_drops_raw_col(spark):
    """The raw_key intermediate must NOT leak into downstream selects."""
    facts = spark.createDataFrame([Row(crime_id=1, raw_key=20240615)])
    dim_keys = spark.createDataFrame([Row(date_key=20240615)])
    out = common.coalesce_to_seeded_date_key(
        facts, dim_keys, raw_col="raw_key", out_col="date_key"
    )
    assert "raw_key" not in out.columns
    assert "date_key" in out.columns


# ---------------------------------------------------------------------------
# dim_location null-NK filter — Codex P1 regression guard
# ---------------------------------------------------------------------------


def test_dim_location_build_dim_rows_filters_null_community_area(spark):
    """A silver row with NULL community_area must NOT appear as a dim
    row. Per dimensional-design.md §8.5 it resolves to location_key=0
    at fact load. Codex PR#2 P1 regression guard.
    """
    from pyspark.sql.types import (
        IntegerType,
        StringType,
        StructField,
        StructType,
    )

    from glue_jobs.silver_to_gold.dimensions import dim_location

    schema = StructType(
        [
            StructField("community_area", IntegerType(), nullable=True),
            StructField("district", IntegerType(), nullable=True),
            StructField("ward", IntegerType(), nullable=True),
            StructField("beat", IntegerType(), nullable=True),
            StructField("block", StringType(), nullable=True),
        ]
    )
    crime = spark.createDataFrame(
        [
            (17, 8, 5, 821, "001XX W RANDOLPH"),  # complete
            (None, 8, 5, 821, "002XX W LAKE"),  # null community_area
            (17, None, None, None, "003XX S STATE"),  # partial null
            (32, 1, 42, 110, "004XX W ROOSEVELT"),  # complete
        ],
        schema=schema,
    )

    out = dim_location.build_dim_rows(crime).collect()
    nks = sorted(
        (r.community_area, r.district, r.ward, r.beat) for r in out
    )
    # Only the two complete rows survive; null/partial-null rows are dropped.
    assert nks == [(17, 8, 5, 821), (32, 1, 42, 110)]
    for r in out:
        assert r.community_area is not None
        assert r.district is not None
        assert r.ward is not None
        assert r.beat is not None
