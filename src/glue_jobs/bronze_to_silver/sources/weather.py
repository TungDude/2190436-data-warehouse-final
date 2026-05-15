"""Bronze -> silver transform for the Open-Meteo Historical Weather API.

The bronze JSON file is columnar (`hourly.time[]`, `hourly.temperature_2m[]`,
parallel arrays), one file per fetched date range. Silver flattens to one
row per hour at the Chicago centroid (41.85, -87.65) and tags WMO codes
into a coarse `weather_category`, plus temp/precip into low-cardinality
bands so the gold `dim_weather` SCD0 rows are slice-friendly.

Source 4 in docs/architecture.md §5. Single hourly grain matches the
dim_weather natural key (`obs_date_key`, `obs_hour`) declared in
silver_to_gold/dimensions/dim_weather.py.
"""

from __future__ import annotations

import logging

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DecimalType,
    ShortType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)


SOURCE_NAME = "weather"
BRONZE_SUBPREFIX = "weather"
SILVER_TABLE_NAME = "weather"

SILVER_PARTITION_COLS = ["_ingest_year"]

_logger = logging.getLogger(__name__)


SILVER_SCHEMA = StructType(
    [
        StructField("obs_time", TimestampType(), nullable=False),
        StructField("temperature_celsius", DecimalType(5, 2), nullable=True),
        StructField("precipitation_mm", DecimalType(6, 2), nullable=True),
        StructField("wind_speed_kmh", DecimalType(5, 2), nullable=True),
        StructField("weather_code_wmo", ShortType(), nullable=True),
        StructField("relative_humidity_pct", DecimalType(5, 2), nullable=True),
        StructField("weather_category", StringType(), nullable=True),
        StructField("temp_band", StringType(), nullable=True),
        StructField("precip_band", StringType(), nullable=True),
        StructField("_ingest_year", ShortType(), nullable=False),
    ]
)


def _bronze_glob(bronze_root_uri: str) -> str:
    return (
        f"{bronze_root_uri.rstrip('/')}/{BRONZE_SUBPREFIX}/"
        "ingest_date=*/*.json"
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
            "No bronze inputs for weather at %s; returning empty DF.",
            glob_path,
        )
        return spark.createDataFrame([], SILVER_SCHEMA)

    raw = spark.read.option("multiLine", True).json(glob_path)

    # Each file has one top-level row whose `hourly` field carries the
    # parallel arrays. arrays_zip pairs them index-wise, posexplode then
    # flattens to one row per hour.
    arrays = raw.select(
        F.col("hourly.time").alias("time_arr"),
        F.col("hourly.temperature_2m").alias("t_arr"),
        F.col("hourly.precipitation").alias("p_arr"),
        F.col("hourly.wind_speed_10m").alias("w_arr"),
        F.col("hourly.weather_code").alias("wc_arr"),
        F.col("hourly.relative_humidity_2m").alias("rh_arr"),
    )

    zipped = arrays.withColumn(
        "z",
        F.arrays_zip(
            F.col("time_arr"),
            F.col("t_arr"),
            F.col("p_arr"),
            F.col("w_arr"),
            F.col("wc_arr"),
            F.col("rh_arr"),
        ),
    ).select(F.explode(F.col("z")).alias("e"))

    df = zipped.select(
        # Open-Meteo timestamps are ISO-8601 without seconds: "2024-06-01T13:00".
        F.to_timestamp(F.col("e.time_arr"), "yyyy-MM-dd'T'HH:mm").alias("obs_time"),
        F.col("e.t_arr").cast(DecimalType(5, 2)).alias("temperature_celsius"),
        F.col("e.p_arr").cast(DecimalType(6, 2)).alias("precipitation_mm"),
        F.col("e.w_arr").cast(DecimalType(5, 2)).alias("wind_speed_kmh"),
        F.col("e.wc_arr").cast(ShortType()).alias("weather_code_wmo"),
        F.col("e.rh_arr").cast(DecimalType(5, 2)).alias("relative_humidity_pct"),
    ).filter(F.col("obs_time").isNotNull())

    # WMO weather codes coarsened to dashboard categories. WMO reference:
    # 0 clear; 1-3 partly cloudy; 45-48 fog; 51-67 rain (drizzle through
    # freezing rain); 71-77 snow; 80-82 rain showers; 85-86 snow showers;
    # 95-99 thunderstorm.
    df = df.withColumn(
        "weather_category",
        F.when(F.col("weather_code_wmo") == 0, F.lit("Clear"))
        .when(F.col("weather_code_wmo").between(1, 3), F.lit("Cloudy"))
        .when(F.col("weather_code_wmo").between(45, 48), F.lit("Fog"))
        .when(F.col("weather_code_wmo").between(51, 67), F.lit("Rain"))
        .when(F.col("weather_code_wmo").between(71, 77), F.lit("Snow"))
        .when(F.col("weather_code_wmo").between(80, 82), F.lit("Rain"))
        .when(F.col("weather_code_wmo").between(85, 86), F.lit("Snow"))
        .when(F.col("weather_code_wmo").between(95, 99), F.lit("Storm"))
        .otherwise(F.lit("Other")),
    )

    df = df.withColumn(
        "temp_band",
        F.when(F.col("temperature_celsius") < 0, F.lit("Freezing"))
        .when(F.col("temperature_celsius") < 10, F.lit("Cold"))
        .when(F.col("temperature_celsius") < 20, F.lit("Mild"))
        .when(F.col("temperature_celsius") < 30, F.lit("Warm"))
        .otherwise(F.lit("Hot")),
    )

    df = df.withColumn(
        "precip_band",
        F.when(F.col("precipitation_mm").isNull(), F.lit("None"))
        .when(F.col("precipitation_mm") == 0, F.lit("None"))
        .when(F.col("precipitation_mm") < 1.0, F.lit("Light"))
        .when(F.col("precipitation_mm") < 5.0, F.lit("Moderate"))
        .otherwise(F.lit("Heavy")),
    )

    df = df.withColumn(
        "_ingest_year", F.year(F.col("obs_time")).cast(ShortType())
    )

    return df.select(*[F.col(field.name) for field in SILVER_SCHEMA.fields])
