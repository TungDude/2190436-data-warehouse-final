"""Bronze -> silver transform for the IUCR crime-code lookup source.

Reads the static IUCR codes CSV (~400 rows) the seeding step uploaded to
``<bronze_root_uri>/iucr_codes/ingest_date=YYYY-MM-DD/*.csv`` and emits
a typed Parquet table at silver. No deduplication needed (CSV is a
canonical snapshot); the table is rewritten in place on each run.
"""

from __future__ import annotations

import logging

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType,
    ShortType,
    StringType,
    StructField,
    StructType,
)

try:  # pragma: no cover
    from common import rename_columns_snake
except ImportError:  # pragma: no cover
    from ..common import rename_columns_snake


SOURCE_NAME = "iucr_codes"
BRONZE_SUBPREFIX = "iucr_codes"
SILVER_TABLE_NAME = "iucr_codes"

# IUCR is a tiny canonical lookup; one partition by ingest year is enough to
# keep the partitioned write API happy. The list will only ever contain a
# couple of years across the project lifetime.
SILVER_PARTITION_COLS = ["_ingest_year"]

_logger = logging.getLogger(__name__)


SILVER_SCHEMA = StructType(
    [
        StructField("iucr", StringType(), nullable=False),
        StructField("primary_description", StringType(), nullable=True),
        StructField("secondary_description", StringType(), nullable=True),
        StructField("index_code", StringType(), nullable=True),
        StructField("active", BooleanType(), nullable=True),
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
            "No bronze inputs for iucr_codes at %s; returning empty DF.",
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

    df = (
        df.withColumn("iucr", F.trim(F.col("iucr")).cast(StringType()))
        .withColumn(
            "primary_description",
            F.col("primary_description").cast(StringType()),
        )
        .withColumn(
            "secondary_description",
            F.col("secondary_description").cast(StringType()),
        )
        .withColumn("index_code", F.upper(F.col("index_code")).cast(StringType()))
        .withColumn(
            "active",
            F.when(F.lower(F.col("active")) == "true", F.lit(True))
            .when(F.lower(F.col("active")) == "false", F.lit(False))
            .otherwise(F.lit(None).cast(BooleanType())),
        )
    )

    # Stable across runs — IUCR is a snapshot, not a transaction stream.
    df = df.filter(F.col("iucr").isNotNull())
    df = df.dropDuplicates(["iucr"])

    # Single partition is fine; the table is < 1k rows.
    df = df.withColumn(
        "_ingest_year", F.year(F.current_date()).cast(ShortType())
    )

    return df.select(*[F.col(field.name) for field in SILVER_SCHEMA.fields])
