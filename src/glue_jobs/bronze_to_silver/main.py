"""Bronze -> silver Glue ETL entry point.

Glue invokes this script as the job's ``script_location``. It dispatches to
a per-source handler (see :mod:`registry`) and writes Parquet to silver,
partitioned by ``SILVER_PARTITION_COLS`` with dynamic-overwrite semantics so
re-runs only rewrite the partitions they touched.

Local tests (``tests/glue_jobs/test_chicago_crime.py``) call the source
handler's ``transform`` function directly and never import this module, so
the only Glue-only symbol below is ``awsglue.utils.getResolvedOptions``.
``test_registry.test_main_dispatches_via_registry`` stubs ``awsglue.utils``
via ``sys.modules`` to exercise the dispatch path without Glue installed.
"""

from __future__ import annotations

import sys

from pyspark.sql import SparkSession

# When Glue executes this script, ``--extra-py-files`` puts the
# bronze_to_silver package on sys.path so a flat ``import registry`` works.
# Locally the test harness imports ``glue_jobs.bronze_to_silver.main`` and
# the package-relative path resolves the same modules.
try:  # pragma: no cover - import path differs between Glue and local
    from registry import get as get_handler
except ImportError:  # pragma: no cover
    from .registry import get as get_handler


REQUIRED_ARGS = [
    "JOB_NAME",
    "source",
    "raw_bucket",
    "raw_prefix",
    "silver_prefix",
]


def build_spark(app_name: str) -> SparkSession:
    return (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .config("spark.sql.parquet.compression.codec", "snappy")
        .getOrCreate()
    )


def main() -> None:
    from awsglue.utils import getResolvedOptions  # type: ignore[import-not-found]

    args = getResolvedOptions(sys.argv, REQUIRED_ARGS)
    handler = get_handler(args["source"])
    spark = build_spark(f"bronze_to_silver:{args['source']}")

    bronze_root_uri = f"s3://{args['raw_bucket']}/{args['raw_prefix']}"
    df = handler.transform(spark=spark, bronze_root_uri=bronze_root_uri)

    silver_path = (
        f"s3://{args['raw_bucket']}/{args['silver_prefix']}/"
        f"{handler.SILVER_TABLE_NAME}/"
    )

    (
        df.write.mode("overwrite")
        .partitionBy(*handler.SILVER_PARTITION_COLS)
        .parquet(silver_path)
    )


if __name__ == "__main__":
    main()
