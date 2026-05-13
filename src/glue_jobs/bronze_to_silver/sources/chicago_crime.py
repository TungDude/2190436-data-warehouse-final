"""Bronze -> silver transform for the Chicago Crime Reports source.

Reads CSVs the existing fetch Lambda wrote to
``<bronze_root_uri>/chicaho_crime/ingest_date=YYYY-MM-DD/*.csv`` (typo in
the bronze prefix preserved by project convention), normalises column names
and types, deduplicates by source ``id`` keeping the latest ``updated_on``
version, and emits a DataFrame partitioned by ``_ingest_year``
(year of the *occurrence* timestamp, not of the ingest date).

``bronze_root_uri`` is a directory URI (no trailing slash required). In Glue
production it looks like ``s3://<bucket>/raw``; in tests it is a local
filesystem path so Spark's CSV reader handles both transparently.
"""

from __future__ import annotations

import logging
from typing import Final

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType,
    DecimalType,
    LongType,
    ShortType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

try:  # pragma: no cover - import path differs between Glue and local
    from common import (
        cast_bool_yn,
        dedup_latest,
        parse_chicago_timestamp,
        rename_columns_snake,
    )
except ImportError:  # pragma: no cover
    from ..common import (
        cast_bool_yn,
        dedup_latest,
        parse_chicago_timestamp,
        rename_columns_snake,
    )


SOURCE_NAME = "chicago_crime"

# Bronze keeps the historical ``chicaho`` typo (we will not rewrite the
# historical backfill). Silver fixes it to the canonical spelling.
#
# This typo is *load-bearing* in three places and they must all stay in sync:
#   - terraform/variables.tf:40   var.raw_chicago_crime_prefix
#   - terraform/lambda_chicago_crime.tf:47   Lambda IAM PutObject scope
#   - this constant
# A rename of the bronze prefix requires changing all three together, plus a
# data move of the existing raw/chicaho_crime/* under the new prefix.
BRONZE_SUBPREFIX = "chicaho_crime"
SILVER_TABLE_NAME = "chicago_crime"

SILVER_PARTITION_COLS = ["_ingest_year"]

# Sentinel year used for rows whose ``date`` failed to parse, so the
# partitioned write does not crash and the bad rows are easy to triage.
# Must fit ``ShortType`` (max 32767), which 9999 does. The gold loader is
# responsible for excluding ``_ingest_year = 9999`` when building dim rows.
_PARTITION_NULL_SENTINEL: Final[int] = 9999

_logger = logging.getLogger(__name__)


# Final silver schema used for both the empty-input fast path and the
# correctness assertions in tests. Order is intentional: it matches the
# transform output column order.
SILVER_SCHEMA = StructType(
    [
        StructField("id", LongType(), nullable=True),
        StructField("case_number", StringType(), nullable=True),
        StructField("date", TimestampType(), nullable=True),
        StructField("block", StringType(), nullable=True),
        StructField("iucr", StringType(), nullable=True),
        StructField("primary_type", StringType(), nullable=True),
        StructField("description", StringType(), nullable=True),
        StructField("location_description", StringType(), nullable=True),
        StructField("arrest", BooleanType(), nullable=True),
        StructField("domestic", BooleanType(), nullable=True),
        StructField("beat", StringType(), nullable=True),
        StructField("district", StringType(), nullable=True),
        StructField("ward", ShortType(), nullable=True),
        StructField("community_area", ShortType(), nullable=True),
        StructField("fbi_code", StringType(), nullable=True),
        StructField("source_year", ShortType(), nullable=True),
        StructField("updated_on", TimestampType(), nullable=True),
        StructField("latitude", DecimalType(9, 6), nullable=True),
        StructField("longitude", DecimalType(9, 6), nullable=True),
        StructField("_ingest_year", ShortType(), nullable=False),
    ]
)


def _bronze_glob(bronze_root_uri: str) -> str:
    return (
        f"{bronze_root_uri.rstrip('/')}/{BRONZE_SUBPREFIX}/"
        "ingest_date=*/*.csv"
    )


def _bronze_input_exists(spark: SparkSession, glob_path: str) -> bool:
    """Hadoop FS check so an empty bronze prefix doesn't crash the read."""
    sc = spark.sparkContext
    hadoop_conf = sc._jsc.hadoopConfiguration()
    fs = sc._jvm.org.apache.hadoop.fs.FileSystem.get(
        sc._jvm.java.net.URI(glob_path), hadoop_conf
    )
    statuses = fs.globStatus(sc._jvm.org.apache.hadoop.fs.Path(glob_path))
    return statuses is not None and len(statuses) > 0


def transform(spark: SparkSession, bronze_root_uri: str) -> DataFrame:
    """Return the silver-ready DataFrame for Chicago Crime Reports."""
    glob_path = _bronze_glob(bronze_root_uri)

    if not _bronze_input_exists(spark, glob_path):
        _logger.warning(
            "No bronze inputs found for chicago_crime at %s; "
            "returning empty DataFrame.",
            glob_path,
        )
        return spark.createDataFrame([], SILVER_SCHEMA)

    raw = (
        spark.read.option("header", True)
        .option("quote", '"')
        .option("escape", '"')
        .option("multiLine", False)
        .option("mode", "PERMISSIVE")
        .csv(glob_path)
    )

    df = rename_columns_snake(raw)

    # Drop columns silver doesn't carry forward.
    for redundant in ("location", "x_coordinate", "y_coordinate"):
        if redundant in df.columns:
            df = df.drop(redundant)

    # Type-cast each retained column. ``trim`` first so accidental whitespace
    # in the source doesn't break casts.
    df = (
        df.withColumn("id", F.col("id").cast(LongType()))
        .withColumn("case_number", F.col("case_number").cast(StringType()))
        .withColumn("date", parse_chicago_timestamp(F.col("date")))
        .withColumn("block", F.col("block").cast(StringType()))
        .withColumn("iucr", F.col("iucr").cast(StringType()))
        .withColumn("primary_type", F.col("primary_type").cast(StringType()))
        .withColumn("description", F.col("description").cast(StringType()))
        .withColumn(
            "location_description",
            F.col("location_description").cast(StringType()),
        )
        .withColumn("arrest", cast_bool_yn(F.col("arrest")))
        .withColumn("domestic", cast_bool_yn(F.col("domestic")))
        # ``beat`` and ``district`` are kept as StringType to preserve zero-
        # padded codes (``"001"``, not ``1``). dim_location in
        # dimensional-design.md §8.3.7 declares them as TEXT — the future
        # silver -> gold loader must treat them as opaque strings, not ints.
        .withColumn("beat", F.col("beat").cast(StringType()))
        .withColumn("district", F.col("district").cast(StringType()))
        .withColumn("ward", F.col("ward").cast(ShortType()))
        .withColumn("community_area", F.col("community_area").cast(ShortType()))
        .withColumn("fbi_code", F.col("fbi_code").cast(StringType()))
        .withColumn("updated_on", parse_chicago_timestamp(F.col("updated_on")))
        .withColumn("latitude", F.col("latitude").cast(DecimalType(9, 6)))
        .withColumn("longitude", F.col("longitude").cast(DecimalType(9, 6)))
    )

    # Source CSV has its own ``year`` column (year of date). Rename it before
    # we add ``_ingest_year`` to keep partition naming explicit.
    if "year" in df.columns:
        df = df.withColumn("source_year", F.col("year").cast(ShortType())).drop(
            "year"
        )
    elif "source_year" not in df.columns:
        df = df.withColumn("source_year", F.lit(None).cast(ShortType()))

    df = dedup_latest(
        df,
        key_cols=["id"],
        order_cols=[
            F.col("updated_on").desc_nulls_last(),
            F.col("date").desc_nulls_last(),
        ],
    )

    df = df.withColumn(
        "_ingest_year",
        F.coalesce(F.year(F.col("date")), F.lit(_PARTITION_NULL_SENTINEL)).cast(
            ShortType()
        ),
    )

    # Project to the silver schema's column order. Any column not produced by
    # the transform (e.g. a brand-new Socrata field) is dropped here.
    return df.select(*[F.col(field.name) for field in SILVER_SCHEMA.fields])
