"""Silver -> gold Glue ETL entry point.

Glue invokes this script as the job's ``script_location``. Dispatch is by
``--target`` (``"dims"`` or ``"facts"``) rather than per-source: the same
script binary backs two Glue Job resources so the workflow's CONDITIONAL
trigger chain (silver crawler SUCCEEDED -> dims, dims SUCCEEDED -> facts)
stays explicit at the resource level.

Local tests under ``tests/glue_jobs/silver_to_gold/`` exercise the dim /
fact modules' ``load()`` functions directly without importing this entry
point, so the only Glue-only symbol below is
``awsglue.utils.getResolvedOptions``.
"""

from __future__ import annotations

import logging
import sys

from pyspark.sql import SparkSession

# Dual-import pattern — see bronze_to_silver/main.py for the rationale.
try:  # pragma: no cover - import path differs between Glue and local
    from common import secret_to_jdbc_props
    from registry import get as get_target
except ImportError:  # pragma: no cover
    from .common import secret_to_jdbc_props
    from .registry import get as get_target


REQUIRED_ARGS = [
    "JOB_NAME",
    "target",
    "silver_database",
    "secret_arn",
    "region",
]

LOGGER = logging.getLogger("silver_to_gold")
LOGGER.setLevel(logging.INFO)


def build_spark(app_name: str) -> SparkSession:
    return (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .config("spark.sql.parquet.compression.codec", "snappy")
        .enableHiveSupport()
        .getOrCreate()
    )


def main() -> None:
    from awsglue.utils import getResolvedOptions  # type: ignore[import-not-found]

    args = getResolvedOptions(sys.argv, REQUIRED_ARGS)
    target = args["target"]
    silver_db = args["silver_database"]
    secret_arn = args["secret_arn"]
    region = args["region"]

    spark = build_spark(f"silver_to_gold:{target}")
    jdbc_props = secret_to_jdbc_props(secret_arn=secret_arn, region=region)

    handlers = get_target(target)
    results = {}
    for module in handlers:
        name = getattr(module, "DIM_NAME", None) or getattr(module, "FACT_NAME")
        LOGGER.info("silver_to_gold %s: loading %s", target, name)
        result = module.load(
            spark=spark,
            jdbc_props=jdbc_props,
            silver_database=silver_db,
        )
        results[name] = result
        LOGGER.info("silver_to_gold %s: %s -> %s", target, name, result)

    LOGGER.info("silver_to_gold %s complete: %s", target, results)


if __name__ == "__main__":  # pragma: no cover
    main()
