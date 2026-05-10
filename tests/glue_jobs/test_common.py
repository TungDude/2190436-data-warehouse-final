"""Unit tests for src/glue_jobs/bronze_to_silver/common.py."""

from __future__ import annotations

import datetime as dt

import pytest
from pyspark.sql import Row, functions as F
from pyspark.sql.types import (
    StringType,
    StructField,
    StructType,
)

from glue_jobs.bronze_to_silver import common


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("X Coordinate", "x_coordinate"),
        ("FBI Code", "fbi_code"),
        ("ID", "id"),
        ("case_number", "case_number"),
        ("camelCaseField", "camel_case_field"),
        ("  Already  Snake_Case  ", "already_snake_case"),
        ("Multiple   Spaces", "multiple_spaces"),
        ("Mixed-Punctuation/Field", "mixed_punctuation_field"),
    ],
)
def test_to_snake_case(raw, expected):
    assert common.to_snake_case(raw) == expected


def test_rename_columns_snake(spark):
    df = spark.createDataFrame(
        [Row(ID=1, **{"Case Number": "JX1", "Primary Type": "THEFT"})]
    )
    renamed = common.rename_columns_snake(df)
    assert set(renamed.columns) == {"id", "case_number", "primary_type"}


def test_parse_chicago_timestamp(spark):
    df = spark.createDataFrame(
        [Row(raw="06/01/2024 02:30:00 PM"), Row(raw="01/02/2024 09:00:00 AM")]
    )
    parsed = df.withColumn("ts", common.parse_chicago_timestamp(F.col("raw")))
    rows = sorted(parsed.collect(), key=lambda r: r.raw)
    assert rows[0].ts == dt.datetime(2024, 1, 2, 9, 0, 0)
    assert rows[1].ts == dt.datetime(2024, 6, 1, 14, 30, 0)


def test_cast_bool_yn(spark):
    schema = StructType([StructField("raw", StringType())])
    df = spark.createDataFrame(
        [
            Row(raw="true"),
            Row(raw="false"),
            Row(raw="TRUE"),
            Row(raw=" False "),
            Row(raw=""),
            Row(raw="banana"),
            Row(raw=None),
        ],
        schema=schema,
    )
    casted = df.withColumn("b", common.cast_bool_yn(F.col("raw"))).collect()
    expected = [True, False, True, False, None, None, None]
    assert [r.b for r in casted] == expected


def test_dedup_latest_keeps_max_order(spark):
    df = spark.createDataFrame(
        [
            Row(id=1, ts="2024-06-01", val="old"),
            Row(id=1, ts="2024-06-05", val="new"),
            Row(id=2, ts="2024-06-02", val="only"),
        ]
    )
    deduped = common.dedup_latest(
        df,
        key_cols=["id"],
        order_cols=[F.col("ts").desc_nulls_last()],
    )
    rows = {r.id: r.val for r in deduped.collect()}
    assert rows == {1: "new", 2: "only"}


def test_dedup_latest_handles_null_ordering(spark):
    """Nulls in the order column must lose to non-null values."""
    df = spark.createDataFrame(
        [Row(id=1, ts=None, val="null_ts"), Row(id=1, ts="2024-06-01", val="real_ts")]
    )
    deduped = common.dedup_latest(
        df,
        key_cols=["id"],
        order_cols=[F.col("ts").desc_nulls_last()],
    )
    assert [r.val for r in deduped.collect()] == ["real_ts"]
