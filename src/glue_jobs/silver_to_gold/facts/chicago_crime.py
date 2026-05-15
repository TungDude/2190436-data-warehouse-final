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
from pyspark.sql.utils import AnalysisException

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
    # read_silver_table already filtered _ingest_year=9999 rows out, so
    # `date` is non-NULL here. The coalesce(...UNKNOWN_DIM_KEY) fallbacks
    # below are belt-and-suspenders against a future silver-layer change
    # that stops triaging unparseable dates to the sentinel partition.

    # ------------------------------------------------------------------
    # FK preparation: derive smart keys and helper columns.
    #
    # Note on `report_date_key`: dimensional-design.md §3.3 names this the
    # "report" date key, but the underlying silver column is `updated_on`
    # (Chicago's "last modification time"). The Chicago Crime feed has no
    # discrete reported-at column distinct from `date`, so the role-playing
    # date dim's "report" role is satisfied by `updated_on` as the closest
    # proxy. Track 6 docs this; do NOT rename without coordinating with
    # the dimensional design.
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
            # After sentinel filtering this is always 0..23 and never falls
            # to UNKNOWN (the .coalesce branch is dead in V1 but kept for
            # the defensive-trim-fail-loud posture from CLAUDE.md).
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
    )

    # Pull the actual temperature / precipitation values from silver weather
    # (joined by date+hour). Source 4 (Open-Meteo) lands here; before it
    # ships, the join misses and both measures stay NULL — which is what
    # the columns held during the V1 pre-weather window.
    try:
        weather_silver = read_silver_table(spark, silver_database, "weather")
        weather_join = weather_silver.select(
            F.date_format(F.col("obs_time"), "yyyyMMdd").cast("int").alias("_w_date_key"),
            F.hour(F.col("obs_time")).cast("smallint").alias("_w_hour"),
            F.col("temperature_celsius").alias("_w_temp"),
            F.col("precipitation_mm").alias("_w_precip"),
        ).dropDuplicates(["_w_date_key", "_w_hour"])

        crime = (
            crime.alias("f")
            .join(
                weather_join.alias("ws"),
                (F.col("f.occurrence_date_key") == F.col("ws._w_date_key"))
                & (F.col("f.occurrence_time_key") == F.col("ws._w_hour")),
                how="left",
            )
            .withColumn(
                "temperature_celsius", F.col("ws._w_temp").cast("decimal(5,2)")
            )
            .withColumn(
                "precipitation_mm", F.col("ws._w_precip").cast("decimal(6,2)")
            )
            .drop("_w_date_key", "_w_hour", "_w_temp", "_w_precip")
        )
    except AnalysisException as exc:
        LOGGER.info(
            "weather silver table not found yet (%s); fact_crime temp/precip "
            "fall back to NULL.",
            exc,
        )
        crime = crime.withColumn(
            "temperature_celsius", F.lit(None).cast("decimal(5,2)")
        ).withColumn("precipitation_mm", F.lit(None).cast("decimal(6,2)"))

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
    # dim_crime_flags is keyed by the boolean source columns. Silver
    # `arrest` / `domestic` can legitimately be NULL (cast_bool_yn returns
    # NULL on garbage). We preserve that null through to the join so a
    # null source -> dim_crime_flags(0) (the (NULL, NULL) reserved row)
    # rather than silently collapsing to "No Arrest, Non-Domestic" which
    # would lose the missing-data signal. The eqNullSafe join + dim
    # row 0's (NULL, NULL) booleans give the correct mapping.
    crime_with_bool = crime.withColumn(
        "_arrest_bool",
        F.when(F.col("arrest").isNull(), F.lit(None).cast("boolean"))
        .when(F.col("arrest") == F.lit(True), F.lit(True))
        .otherwise(F.lit(False)),
    ).withColumn(
        "_domestic_bool",
        F.when(F.col("domestic").isNull(), F.lit(None).cast("boolean"))
        .when(F.col("domestic") == F.lit(True), F.lit(True))
        .otherwise(F.lit(False)),
    )
    crime = (
        crime_with_bool.alias("f")
        .join(
            dim_crime_flags.alias("fl"),
            (F.col("f._arrest_bool").eqNullSafe(F.col("fl._flags_is_arrest")))
            & (F.col("f._domestic_bool").eqNullSafe(F.col("fl._flags_is_domestic"))),
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
