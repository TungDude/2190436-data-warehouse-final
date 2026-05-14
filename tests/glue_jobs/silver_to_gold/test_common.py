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
