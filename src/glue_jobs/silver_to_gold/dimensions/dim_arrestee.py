"""Loader stub for ``dw.dim_arrestee`` (SCD1).

V1 is a no-op: source 5 (Chicago Police Arrests) is deferred, so the
dim has no rows and ``fact_arrest`` is not loaded either
(``docs/dimensional-design.md`` §10.2 Q1, ``docs/silver-to-gold-plan.md``
§6 Q1).

The module stays in ``registry.TARGETS["dims"]`` so the workflow shape
matches the dimensional design even before source 5 ships.
"""

from __future__ import annotations

import logging

from pyspark.sql import SparkSession

LOGGER = logging.getLogger(__name__)

DIM_NAME = "dim_arrestee"
SCD_TYPE = 1
TARGET_TABLE = "dw.dim_arrestee"
STAGING_TABLE = "dw_staging.scd1_dim_arrestee_inflight"

NATURAL_KEY = ["race", "age_band", "sex"]
TRACKED_COLS: list[str] = []
ATTRIBUTE_COLS = ["race", "age_band", "sex"]


def load(
    spark: SparkSession,
    jdbc_props: dict[str, str],
    silver_database: str,
) -> dict[str, int]:
    LOGGER.info(
        "dim_arrestee load skipped — source 5 (Chicago Police Arrests) not "
        "yet in silver. fact_arrest is also deferred until source 5 lands."
    )
    return {"skipped": 1}
