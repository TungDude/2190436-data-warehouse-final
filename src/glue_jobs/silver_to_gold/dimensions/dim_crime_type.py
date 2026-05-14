"""Loader for ``dw.dim_crime_type`` (SCD2).

V1 reads ``(iucr, primary_type, description, fbi_code)`` distinct from
silver ``chicago_crime``. The ``index_code`` and ``active`` columns
arrive when source 2 (IUCR Crime Codes) lands in silver — until then
they default to ``NULL`` and ``TRUE`` per the DDL in
``sql/dw_schema.sql``.
"""

from __future__ import annotations

import logging

from pyspark.sql import DataFrame, SparkSession

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

# These attribute changes flip an IUCR row to a new SCD2 version.
# index_code / active are NOT tracked yet because their feeder (source 2)
# hasn't landed; append them here when source 2 ships and the SCD2 contract
# follows automatically.
TRACKED_COLS = ["primary_type", "description", "fbi_code"]

ATTRIBUTE_COLS = ["iucr", "primary_type", "description", "fbi_code"]


def load(
    spark: SparkSession,
    jdbc_props: dict[str, str],
    silver_database: str,
) -> dict[str, int]:
    crime = read_silver_table(spark, silver_database, "chicago_crime")

    df_new = (
        crime.select(*ATTRIBUTE_COLS)
        .where("iucr IS NOT NULL")  # null IUCR -> dim_crime_type_key=0 at fact load
        .dropDuplicates(NATURAL_KEY)
    )

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
