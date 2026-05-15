"""Loader for ``dw.dim_weather`` (SCD0, one row per hour at the Chicago
centroid).

Reads silver ``weather`` (already flattened from Open-Meteo's columnar
JSON, see ``bronze_to_silver/sources/weather.py``) and upserts into
``dw.dim_weather`` by the conformed natural key (``obs_date_key``,
``obs_hour``). The sentinel row at ``weather_key = -1`` ("Weather
observation not available") seeded by ``sql/dw_seed.sql`` is left in
place — fact rows whose weather lookup returns no match still fall to
it.
"""

from __future__ import annotations

import logging

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.utils import AnalysisException

try:  # pragma: no cover
    from common import read_silver_table, scd1_upsert
except ImportError:  # pragma: no cover
    from ..common import read_silver_table, scd1_upsert

LOGGER = logging.getLogger(__name__)

DIM_NAME = "dim_weather"
SCD_TYPE = 0
TARGET_TABLE = "dw.dim_weather"
STAGING_TABLE = "dw_staging.scd0_dim_weather_inflight"

NATURAL_KEY = ["obs_date_key", "obs_hour"]
TRACKED_COLS: list[str] = []
ATTRIBUTE_COLS = [
    "obs_date_key",
    "obs_hour",
    "weather_code_wmo",
    "weather_category",
    "temp_band",
    "precip_band",
]


def load(
    spark: SparkSession,
    jdbc_props: dict[str, str],
    silver_database: str,
) -> dict[str, int]:
    try:
        silver = read_silver_table(spark, silver_database, "weather")
    except AnalysisException as exc:
        LOGGER.info(
            "weather silver table not found yet (%s); leaving dim_weather "
            "with the seeded sentinel row only.",
            exc,
        )
        return {"skipped": 1}

    df_new = silver.select(
        F.date_format(F.col("obs_time"), "yyyyMMdd").cast("integer").alias(
            "obs_date_key"
        ),
        F.hour(F.col("obs_time")).cast("short").alias("obs_hour"),
        F.col("weather_code_wmo"),
        F.col("weather_category"),
        F.col("temp_band"),
        F.col("precip_band"),
    ).dropDuplicates(NATURAL_KEY)

    df_new = df_new.filter(F.col("obs_date_key").isNotNull())

    count = df_new.count()
    if count == 0:
        LOGGER.info("weather silver table is empty; nothing to upsert.")
        return {"upserted": 0}

    LOGGER.info("dim_weather: upserting %d distinct (date,hour) rows", count)

    return scd1_upsert(
        spark,
        jdbc_props,
        target_table=TARGET_TABLE,
        staging_table=STAGING_TABLE,
        df_new=df_new,
        natural_key=NATURAL_KEY,
    )
