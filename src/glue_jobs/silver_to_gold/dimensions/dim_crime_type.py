"""Loader for ``dw.dim_crime_type`` (SCD2).

Reads (iucr, primary_type, description, fbi_code) from silver
``chicago_crime`` and left-joins silver ``iucr_codes`` to enrich
``index_code`` (Index Crime classification: 'I'/'N') and ``active``.

When the IUCR lookup is absent (silver table missing or empty), the
loader falls back to NULL index_code / TRUE active per the DDL defaults
in ``sql/dw_schema.sql``.
"""

from __future__ import annotations

import logging

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.utils import AnalysisException

try:  # pragma: no cover
    from common import read_silver_table, scd2_merge
except ImportError:  # pragma: no cover
    from ..common import read_silver_table, scd2_merge

LOGGER = logging.getLogger(__name__)

DIM_NAME = "dim_crime_type"
SCD_TYPE = 2
TARGET_TABLE = "dw.dim_crime_type"
STAGING_TABLE = "dw_staging.scd2_dim_crime_type_inflight"

NATURAL_KEY = ["iucr"]

# index_code / active become SCD2-tracked once the IUCR feeder lands.
TRACKED_COLS = ["primary_type", "description", "fbi_code", "index_code", "active"]

ATTRIBUTE_COLS = [
    "iucr",
    "primary_type",
    "description",
    "fbi_code",
    "index_code",
    "active",
]


def _read_iucr_lookup(spark: SparkSession, silver_database: str) -> DataFrame | None:
    """Return the IUCR silver DF, or None if the catalog table is missing."""
    try:
        return read_silver_table(spark, silver_database, "iucr_codes")
    except AnalysisException as exc:
        LOGGER.info(
            "iucr_codes silver table not found yet (%s); falling back to NULL "
            "index_code / TRUE active.",
            exc,
        )
        return None


def load(
    spark: SparkSession,
    jdbc_props: dict[str, str],
    silver_database: str,
) -> dict[str, int]:
    crime = read_silver_table(spark, silver_database, "chicago_crime")
    iucr = _read_iucr_lookup(spark, silver_database)

    base = (
        crime.select("iucr", "primary_type", "description", "fbi_code")
        .where("iucr IS NOT NULL")
        .dropDuplicates(NATURAL_KEY)
    )

    if iucr is None:
        df_new = base.withColumn(
            "index_code", F.lit(None).cast("string")
        ).withColumn("active", F.lit(True))
    else:
        iucr_proj = iucr.select(
            F.col("iucr").alias("iucr_lookup"),
            F.col("index_code"),
            F.col("active"),
        )
        df_new = (
            base.join(
                iucr_proj,
                base["iucr"] == iucr_proj["iucr_lookup"],
                how="left",
            )
            .drop("iucr_lookup")
            .withColumn(
                "active",
                F.when(F.col("active").isNull(), F.lit(True)).otherwise(F.col("active")),
            )
        )

    df_new = df_new.select(*ATTRIBUTE_COLS)

    LOGGER.info("dim_crime_type: %d distinct IUCR codes", df_new.count())

    return scd2_merge(
        spark,
        jdbc_props,
        target_table=TARGET_TABLE,
        staging_table=STAGING_TABLE,
        df_new=df_new,
        natural_key=NATURAL_KEY,
        tracked_cols=TRACKED_COLS,
        attribute_cols=ATTRIBUTE_COLS,
    )
