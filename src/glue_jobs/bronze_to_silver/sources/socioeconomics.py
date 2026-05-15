"""Bronze -> silver transform for the Chicago Community Area Socioeconomics
lookup source (~77 rows per snapshot).

One row per Chicago community area; the snapshot represents the most recent
ACS/census release the project ingested. Re-running this transform
overwrites the silver table with the latest snapshot — dim_location's SCD2
loader is responsible for materialising a new version when these attributes
change between snapshots.
"""

from __future__ import annotations

import logging

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DecimalType,
    IntegerType,
    ShortType,
    StringType,
    StructField,
    StructType,
)

try:  # pragma: no cover
    from common import rename_columns_snake
except ImportError:  # pragma: no cover
    from ..common import rename_columns_snake


SOURCE_NAME = "socioeconomics"
BRONZE_SUBPREFIX = "socioeconomics"
SILVER_TABLE_NAME = "socioeconomics"

SILVER_PARTITION_COLS = ["_ingest_year"]

_logger = logging.getLogger(__name__)


SILVER_SCHEMA = StructType(
    [
        StructField("community_area", ShortType(), nullable=False),
        StructField("community_area_name", StringType(), nullable=True),
        StructField("pct_housing_crowded", DecimalType(5, 2), nullable=True),
        StructField("pct_below_poverty", DecimalType(5, 2), nullable=True),
        StructField("pct_unemployed_16plus", DecimalType(5, 2), nullable=True),
        StructField("pct_no_hs_25plus", DecimalType(5, 2), nullable=True),
        StructField("pct_under18_or_over64", DecimalType(5, 2), nullable=True),
        StructField("per_capita_income_usd", IntegerType(), nullable=True),
        StructField("hardship_index", ShortType(), nullable=True),
        StructField("_ingest_year", ShortType(), nullable=False),
    ]
)


def _bronze_glob(bronze_root_uri: str) -> str:
    return (
        f"{bronze_root_uri.rstrip('/')}/{BRONZE_SUBPREFIX}/"
        "ingest_date=*/*.csv"
    )


def _bronze_input_exists(spark: SparkSession, glob_path: str) -> bool:
    sc = spark.sparkContext
    hadoop_conf = sc._jsc.hadoopConfiguration()
    fs = sc._jvm.org.apache.hadoop.fs.FileSystem.get(
        sc._jvm.java.net.URI(glob_path), hadoop_conf
    )
    statuses = fs.globStatus(sc._jvm.org.apache.hadoop.fs.Path(glob_path))
    return statuses is not None and len(statuses) > 0


def transform(spark: SparkSession, bronze_root_uri: str) -> DataFrame:
    glob_path = _bronze_glob(bronze_root_uri)

    if not _bronze_input_exists(spark, glob_path):
        _logger.warning(
            "No bronze inputs for socioeconomics at %s; returning empty DF.",
            glob_path,
        )
        return spark.createDataFrame([], SILVER_SCHEMA)

    raw = (
        spark.read.option("header", True)
        .option("quote", '"')
        .option("escape", '"')
        .option("mode", "PERMISSIVE")
        .csv(glob_path)
    )

    df = rename_columns_snake(raw)

    # The portal column `ca` is the community-area number; rename for clarity.
    # The portal column `per_capita_income_` has a trailing underscore that
    # to_snake_case() strips, so the post-rename name we work with is
    # `per_capita_income` (no trailing _).
    rename_map = {
        "ca": "community_area",
        "percent_of_housing_crowded": "pct_housing_crowded",
        "percent_households_below_poverty": "pct_below_poverty",
        "percent_aged_16_unemployed": "pct_unemployed_16plus",
        "percent_aged_25_without_high_school_diploma": "pct_no_hs_25plus",
        "percent_aged_under_18_or_over_64": "pct_under18_or_over64",
        "per_capita_income": "per_capita_income_usd",
    }
    for old, new in rename_map.items():
        if old in df.columns:
            df = df.withColumnRenamed(old, new)

    df = (
        df.withColumn("community_area", F.col("community_area").cast(ShortType()))
        .withColumn(
            "community_area_name", F.col("community_area_name").cast(StringType())
        )
        .withColumn(
            "pct_housing_crowded",
            F.col("pct_housing_crowded").cast(DecimalType(5, 2)),
        )
        .withColumn(
            "pct_below_poverty",
            F.col("pct_below_poverty").cast(DecimalType(5, 2)),
        )
        .withColumn(
            "pct_unemployed_16plus",
            F.col("pct_unemployed_16plus").cast(DecimalType(5, 2)),
        )
        .withColumn(
            "pct_no_hs_25plus",
            F.col("pct_no_hs_25plus").cast(DecimalType(5, 2)),
        )
        .withColumn(
            "pct_under18_or_over64",
            F.col("pct_under18_or_over64").cast(DecimalType(5, 2)),
        )
        .withColumn(
            "per_capita_income_usd",
            F.col("per_capita_income_usd").cast(IntegerType()),
        )
        .withColumn("hardship_index", F.col("hardship_index").cast(ShortType()))
        .filter(F.col("community_area").isNotNull())
        .dropDuplicates(["community_area"])
        .withColumn(
            "_ingest_year",
            F.year(F.current_date()).cast(ShortType()),
        )
    )

    return df.select(*[F.col(field.name) for field in SILVER_SCHEMA.fields])
