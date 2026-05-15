"""Loader for ``dw.dim_location`` (SCD2 with embedded Type 1 attributes).

Reads the geographic natural key from silver ``chicago_crime`` and
left-joins silver ``socioeconomics`` by ``community_area`` to populate
``community_area_name`` and the seven SCD2-tracked socioeconomic
attributes (poverty %, hardship index, per-capita income, etc.).

When the socioeconomics silver table is absent or empty, the loader falls
back to NULL for all enrichment columns — matching the V0 behaviour that
seeded the dim with the geographic natural key only.
"""

from __future__ import annotations

import logging

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.utils import AnalysisException

try:  # pragma: no cover
    from common import _psycopg_connect, read_silver_table, scd2_merge
except ImportError:  # pragma: no cover
    from ..common import _psycopg_connect, read_silver_table, scd2_merge

LOGGER = logging.getLogger(__name__)

DIM_NAME = "dim_location"
SCD_TYPE = 2
TARGET_TABLE = "dw.dim_location"
STAGING_TABLE = "dw_staging.scd2_dim_location_inflight"

NATURAL_KEY = ["community_area", "district", "ward", "beat"]

# When these change, the SCD2 merge expires the current row and inserts a
# new one. community_area_name is SCD1-overwrite per the dimensional design,
# so it stays out of TRACKED_COLS — it is written into the existing row in
# place via the scd2_merge attribute update.
TRACKED_COLS = [
    "pct_housing_crowded",
    "pct_below_poverty",
    "pct_unemployed_16plus",
    "pct_no_hs_25plus",
    "pct_under18_or_over64",
    "per_capita_income_usd",
    "hardship_index",
]

ATTRIBUTE_COLS = [
    "community_area",
    "district",
    "ward",
    "beat",
    "block",
    "community_area_name",
    *TRACKED_COLS,
]


def _read_socioeconomics(spark: SparkSession, silver_database: str) -> DataFrame | None:
    """Return the socio silver DF, or None if the catalog table is missing.

    Empty-table detection (df.head(1) == []) is intentionally NOT used here
    — it can return false-empty when the Glue Catalog entry is fresh and
    Spark's metastore cache is still stale. Better to let the downstream
    left-join surface an empty socio cleanly than to skip enrichment on a
    racy emptiness check.
    """
    try:
        return read_silver_table(spark, silver_database, "socioeconomics")
    except AnalysisException as exc:
        LOGGER.info(
            "socioeconomics silver table not found yet (%s); leaving "
            "enrichment columns NULL.",
            exc,
        )
        return None


def load(
    spark: SparkSession,
    jdbc_props: dict[str, str],
    silver_database: str,
) -> dict[str, int]:
    crime = read_silver_table(spark, silver_database, "chicago_crime")
    socio = _read_socioeconomics(spark, silver_database)

    base = (
        crime.select(*NATURAL_KEY)
        .dropDuplicates(NATURAL_KEY)
        .withColumn("block", F.lit(None).cast("string"))
    )

    if socio is None:
        df_new = base.withColumn(
            "community_area_name", F.lit(None).cast("string")
        )
        # Explicit casts on each fallback column: F.lit(None) without a
        # cast produces a void-typed column that compute_scd_hash's
        # F.col(c).cast("string") then fails to find by name in some
        # Spark versions. Casting up-front pins the schema deterministically.
        _tracked_types = {
            "pct_housing_crowded": "decimal(5,2)",
            "pct_below_poverty": "decimal(5,2)",
            "pct_unemployed_16plus": "decimal(5,2)",
            "pct_no_hs_25plus": "decimal(5,2)",
            "pct_under18_or_over64": "decimal(5,2)",
            "per_capita_income_usd": "integer",
            "hardship_index": "smallint",
        }
        for col, dtype in _tracked_types.items():
            df_new = df_new.withColumn(col, F.lit(None).cast(dtype))
    else:
        socio_proj = socio.select(
            F.col("community_area").alias("socio_ca"),
            F.col("community_area_name"),
            F.col("pct_housing_crowded"),
            F.col("pct_below_poverty"),
            F.col("pct_unemployed_16plus"),
            F.col("pct_no_hs_25plus"),
            F.col("pct_under18_or_over64"),
            F.col("per_capita_income_usd"),
            F.col("hardship_index"),
        )
        df_new = base.join(
            socio_proj,
            base["community_area"] == socio_proj["socio_ca"],
            how="left",
        ).drop("socio_ca")

    df_new = df_new.select(*ATTRIBUTE_COLS)

    LOGGER.info("dim_location: %d distinct natural keys", df_new.count())

    merge_counts = scd2_merge(
        spark,
        jdbc_props,
        target_table=TARGET_TABLE,
        staging_table=STAGING_TABLE,
        df_new=df_new,
        natural_key=NATURAL_KEY,
        tracked_cols=TRACKED_COLS,
        attribute_cols=ATTRIBUTE_COLS,
    )

    # community_area_name is "embedded SCD1 inside SCD2" per
    # docs/dimensional-design.md §3.5 ("dim_location uses SCD2 with embedded
    # Type 1 attributes"). scd2_merge above only writes new versions —
    # historical versions of the same community_area keep their original
    # community_area_name (NULL during V0, before source 3 landed).
    #
    # Without this propagation, fact rows that resolve via SCD2 to a v1
    # dim row see community_area_name=NULL and the dashboards coalesce to
    # "Unknown" for every row. The UPDATE below copies the current-version
    # name onto all historical versions of the same community_area so SCD1
    # semantics hold across the SCD2 version chain.
    _propagate_community_area_name(jdbc_props)

    return merge_counts


def _propagate_community_area_name(jdbc_props: dict[str, str]) -> None:
    """Copy ``community_area_name`` from the current SCD2 version to all
    historical versions of the same ``community_area``. Idempotent.
    """
    sql = """
        UPDATE dw.dim_location AS old
           SET community_area_name = src.community_area_name
          FROM dw.dim_location AS src
         WHERE old.community_area = src.community_area
           AND old.community_area IS NOT NULL
           AND src.is_current = TRUE
           AND src.community_area_name IS NOT NULL
           AND (old.community_area_name IS DISTINCT FROM src.community_area_name)
    """
    with _psycopg_connect(jdbc_props) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            propagated = cur.rowcount
        conn.commit()
    LOGGER.info(
        "dim_location: propagated community_area_name to %d historical rows",
        propagated,
    )
