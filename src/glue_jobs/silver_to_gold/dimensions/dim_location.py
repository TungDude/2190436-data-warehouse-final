"""Loader for ``dw.dim_location`` (SCD2 with embedded Type 1 attributes).

V1 reads the geographic natural key from silver ``chicago_crime``. The
socioeconomic SCD2-tracked columns (``pct_*``, ``per_capita_income_usd``,
``hardship_index``, ``community_area_name``) arrive when source 3
(Community Area Socioeconomics) lands in silver — until then,
``TRACKED_COLS`` is empty so :func:`common.scd2_merge` performs
insert-once-per-natural-key semantics, which is the documented null-FK
contract from ``docs/dimensional-design.md`` §8.5.
"""

from __future__ import annotations

import logging

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

try:  # pragma: no cover
    from common import read_silver_table, scd2_merge
except ImportError:  # pragma: no cover
    from ..common import read_silver_table, scd2_merge

LOGGER = logging.getLogger(__name__)

DIM_NAME = "dim_location"
SCD_TYPE = 2
TARGET_TABLE = "dw.dim_location"
STAGING_TABLE = "dw_staging.scd2_dim_location_inflight"

NATURAL_KEY = ["community_area", "district", "ward", "beat"]

# V1: no SCD2-tracked attribute columns. Socioeconomic columns arrive with
# source 3. When they do, append them here; the merge contract stays the
# same.
TRACKED_COLS: list[str] = []

# Attribute columns written to dw.dim_location alongside the natural key.
# block is intentionally left NULL in V1: the current natural key is
# community_area/district/ward/beat, and many blocks can exist inside one such
# key. Selecting an arbitrary block during dropDuplicates would make the dim
# nondeterministic. community_area_name arrives with source 3.
ATTRIBUTE_COLS = [
    "community_area",
    "district",
    "ward",
    "beat",
    "block",
    "community_area_name",
]


def build_dim_rows(crime: DataFrame) -> DataFrame:
    """Build the distinct dim_location source rows from silver chicago_crime.

    Reserved-Unknown contract (docs/dimensional-design.md §8.5): any
    silver row with a partial-null natural key MUST route to
    ``location_key=0`` at fact load, not become its own dim row.
    Allowing a NULL-NK tuple to land in the dim would make
    :func:`common.resolve_scd2_fk_asof` match facts to it via
    ``eqNullSafe`` instead of falling to the reserved Unknown
    surrogate, corrupting analytics on missing-location incidents.
    So we drop them at source.

    ``block`` and ``community_area_name`` are force-NULL'd post-dedup
    so a re-run produces a deterministic dim (block has many values per
    NK in silver; picking one arbitrarily would churn the hash on every
    load).

    Extracted from :func:`load` so it can be unit-tested without a
    Postgres connection.
    """
    nk_not_null = F.lit(True)
    for nk in NATURAL_KEY:
        nk_not_null = nk_not_null & F.col(nk).isNotNull()

    return (
        crime.filter(nk_not_null)
        .select(*NATURAL_KEY)
        .dropDuplicates(NATURAL_KEY)
        .withColumn("block", F.lit(None).cast("string"))
        .withColumn("community_area_name", F.lit(None).cast("string"))
        .select(*ATTRIBUTE_COLS)
    )


def load(
    spark: SparkSession,
    jdbc_props: dict[str, str],
    silver_database: str,
) -> dict[str, int]:
    crime = read_silver_table(spark, silver_database, "chicago_crime")
    df_new = build_dim_rows(crime)

    LOGGER.info("dim_location: %d distinct natural keys", df_new.count())

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
