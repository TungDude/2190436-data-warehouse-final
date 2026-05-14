"""Loader stub for ``dw.dim_weather`` (SCD0).

V1 is a no-op: the dim only contains the reserved ``weather_key = -1``
"Weather observation not available" row seeded by ``sql/dw_seed.sql``.
When source 4 (Open-Meteo Historical Weather) lands in silver, replace
``load()`` with the actual ``scd0_insert_only`` call.

The module stays in ``registry.TARGETS["dims"]`` so the workflow's dim
phase always exercises the same module list; the no-op shape keeps
``fact_crime.weather_key`` resolution falling to ``-1`` until source 4
ships.
"""

from __future__ import annotations

import logging

from pyspark.sql import SparkSession

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
    LOGGER.info(
        "dim_weather load skipped — source 4 (Open-Meteo) not yet in silver. "
        "The reserved weather_key=-1 row seeded by dw_seed.sql absorbs every "
        "fact-crime weather FK lookup until then."
    )
    return {"skipped": 1}
