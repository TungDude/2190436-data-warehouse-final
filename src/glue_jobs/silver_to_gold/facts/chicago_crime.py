"""Loader for ``dw.fact_crime`` — atomic transaction-grain fact.

Reads silver ``chicago_crime`` (sentinel ``_ingest_year = 9999``
excluded), resolves every conformed-dim FK against the gold dims, and
idempotently upserts by ``crime_id`` (the natural key per
``docs/dimensional-design.md`` §3.2.1).

FK coalescence is non-negotiable: any null lookup falls to the
reserved-Unknown surrogate (``0`` for every dim except ``dim_weather``
which uses ``-1``). The fact row is NEVER dropped — silver is "triage,
not refuse" (CLAUDE.md Silver-Layer section); gold honours the same
posture.
"""

from __future__ import annotations

import logging

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

try:  # pragma: no cover
    from common import (
        fact_upsert,
        jdbc_read_table,
        read_silver_table,
        resolve_scd2_fk_asof,
    )
except ImportError:  # pragma: no cover
    from ..common import (
        fact_upsert,
        jdbc_read_table,
        read_silver_table,
        resolve_scd2_fk_asof,
    )

LOGGER = logging.getLogger(__name__)

FACT_NAME = "fact_crime"
TARGET_TABLE = "dw.fact_crime"
STAGING_TABLE = "dw_staging.fact_crime_inflight"
NATURAL_KEY = ["crime_id"]

# Reserved Unknown / Not-applicable surrogates from dimensional-design.md §8.5.
UNKNOWN_DIM_KEY = 0
WEATHER_NOT_AVAILABLE_KEY = -1

# Columns of dw.fact_crime in the order they are inserted. Must match the
# DDL in sql/dw_schema.sql §8.3.7 exactly so the JDBC staging table maps
# cleanly to fact_crime.
FACT_COLS = [
    "crime_id",
    "case_number",
    "occurrence_date_key",
    "occurrence_time_key",
    "report_date_key",
    "location_key",
    "crime_type_key",
    "weather_key",
    "flags_key",
    "incident_count",
    "is_arrest",
    "is_domestic",
    "hours_to_update",
    "latitude",
    "longitude",
    "temperature_celsius",
    "precipitation_mm",
]


def load(
    spark: SparkSession,
    jdbc_props: dict[str, str],
    silver_database: str,
) -> dict[str, int]:
    crime = read_silver_table(spark, silver_database, "chicago_crime")

    # ------------------------------------------------------------------
    # FK preparation: derive smart keys and helper columns.
    # ------------------------------------------------------------------
    crime = (
        crime.withColumn("occurrence_date", F.to_date("date"))
        .withColumn(
            "occurrence_date_key",
            F.coalesce(
                (F.year("date") * 10000 + F.month("date") * 100 + F.dayofmonth("date")).cast("int"),
                F.lit(UNKNOWN_DIM_KEY),
            ),
        )
        .withColumn(
            "occurrence_time_key",
            F.coalesce(F.hour("date").cast("smallint"), F.lit(UNKNOWN_DIM_KEY).cast("smallint")),
        )
        .withColumn(
            "report_date_key",
            F.coalesce(
                (F.year("updated_on") * 10000 + F.month("updated_on") * 100 + F.dayofmonth("updated_on")).cast("int"),
                F.lit(UNKNOWN_DIM_KEY),
            ),
        )
        .withColumn(
            "hours_to_update",
            F.when(
                F.col("updated_on").isNotNull() & F.col("date").isNotNull(),
                ((F.unix_timestamp("updated_on") - F.unix_timestamp("date")) / 3600).cast("int"),
            ).otherwise(F.lit(None).cast("int")),
        )
        .withColumn("incident_count", F.lit(1).cast("smallint"))
        .withColumn(
            "is_arrest",
            F.when(F.col("arrest") == F.lit(True), F.lit(1).cast("smallint"))
            .when(F.col("arrest") == F.lit(False), F.lit(0).cast("smallint"))
            .otherwise(F.lit(0).cast("smallint")),
        )
        .withColumn(
            "is_domestic",
            F.when(F.col("domestic") == F.lit(True), F.lit(1).cast("smallint"))
            .when(F.col("domestic") == F.lit(False), F.lit(0).cast("smallint"))
            .otherwise(F.lit(0).cast("smallint")),
        )
        .withColumn("temperature_celsius", F.lit(None).cast("decimal(5,2)"))
        .withColumn("precipitation_mm", F.lit(None).cast("decimal(6,2)"))
    )

    # ------------------------------------------------------------------
    # SCD2 FK lookups against the just-loaded dim tables.
    # ------------------------------------------------------------------
    dim_location = (
        jdbc_read_table(spark, jdbc_props, "dw.dim_location")
        .select(
            "location_key",
            "community_area",
            "district",
            "ward",
            "beat",
            "scd_start_date",
            "scd_end_date",
        )
    )
    crime = resolve_scd2_fk_asof(
        crime,
        dim_location,
        natural_key=["community_area", "district", "ward", "beat"],
        event_date_col="occurrence_date",
        dim_key_col="location_key",
        unknown_key=UNKNOWN_DIM_KEY,
    )

    dim_crime_type = (
        jdbc_read_table(spark, jdbc_props, "dw.dim_crime_type")
        .select("crime_type_key", "iucr", "scd_start_date", "scd_end_date")
    )
    crime = resolve_scd2_fk_asof(
        crime,
        dim_crime_type,
        natural_key=["iucr"],
        event_date_col="occurrence_date",
        dim_key_col="crime_type_key",
        unknown_key=UNKNOWN_DIM_KEY,
    )

    # ------------------------------------------------------------------
    # Lookups against SCD0 / SCD1 dims (no scd_*_date range, just NK match).
    # ------------------------------------------------------------------
    dim_weather = (
        jdbc_read_table(spark, jdbc_props, "dw.dim_weather")
        .select("weather_key", "obs_date_key", "obs_hour")
    )
    crime = (
        crime.alias("f")
        .join(
            dim_weather.alias("w"),
            (F.col("f.occurrence_date_key") == F.col("w.obs_date_key"))
            & (F.col("f.occurrence_time_key") == F.col("w.obs_hour")),
            how="left",
        )
        .withColumn(
            "weather_key",
            F.coalesce(F.col("w.weather_key"), F.lit(WEATHER_NOT_AVAILABLE_KEY)),
        )
        .select("f.*", "weather_key")
    )

    dim_crime_flags = (
        jdbc_read_table(spark, jdbc_props, "dw.dim_crime_flags")
        .select("flags_key", "is_arrest", "is_domestic")
        .withColumnRenamed("is_arrest", "_flags_is_arrest")
        .withColumnRenamed("is_domestic", "_flags_is_domestic")
    )
    # dim_crime_flags maps the boolean source columns; we already cast
    # arrest/domestic to SMALLINT for the additive fact measures. Convert
    # back to boolean for the join.
    crime_with_bool = crime.withColumn(
        "_arrest_bool", F.col("is_arrest") == 1
    ).withColumn("_domestic_bool", F.col("is_domestic") == 1)
    crime = (
        crime_with_bool.alias("f")
        .join(
            dim_crime_flags.alias("fl"),
            (F.col("f._arrest_bool") == F.col("fl._flags_is_arrest"))
            & (F.col("f._domestic_bool") == F.col("fl._flags_is_domestic")),
            how="left",
        )
        .withColumn(
            "flags_key",
            F.coalesce(F.col("fl.flags_key").cast("smallint"), F.lit(UNKNOWN_DIM_KEY).cast("smallint")),
        )
        .drop("_arrest_bool", "_domestic_bool")
        .select("f.*", "flags_key")
    )

    # ------------------------------------------------------------------
    # Cast crime_id to BIGINT (matches the natural-key column type in
    # fact_crime) and rename id -> crime_id.
    # ------------------------------------------------------------------
    crime = crime.withColumnRenamed("id", "crime_id").withColumn(
        "crime_id", F.col("crime_id").cast("bigint")
    )

    df_facts = crime.select(*FACT_COLS)

    LOGGER.info("fact_crime: upserting %d rows", df_facts.count())

    return fact_upsert(
        spark,
        jdbc_props,
        target_table=TARGET_TABLE,
        staging_table=STAGING_TABLE,
        df_new=df_facts,
        natural_key=NATURAL_KEY,
    )
