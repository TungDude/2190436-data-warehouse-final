"""Tests for the source dispatch registry and main.py argv plumbing."""

from __future__ import annotations

import sys
import types

import pytest

from glue_jobs.bronze_to_silver import registry
from glue_jobs.bronze_to_silver.sources import chicago_crime


def test_known_source_returns_handler():
    assert registry.get("chicago_crime") is chicago_crime


def test_unknown_source_raises_with_helpful_message():
    with pytest.raises(ValueError, match="Unknown source 'bogus'"):
        registry.get("bogus")


def test_unknown_source_lists_known_sources():
    with pytest.raises(ValueError, match=r"Known sources: \[chicago_crime\]"):
        registry.get("nope")


def test_main_dispatches_via_registry(monkeypatch, spark):
    """Stub awsglue.utils + the silver writer so we can drive main.py
    without Glue installed and without writing to S3."""

    fake_awsglue = types.ModuleType("awsglue")
    fake_awsglue_utils = types.ModuleType("awsglue.utils")

    glue_args = {
        "JOB_NAME": "data-warehouse-final-bronze-to-silver",
        "source": "chicago_crime",
        "raw_bucket": "test-bucket",
        "raw_prefix": "raw",
        "silver_prefix": "standardized",
    }
    fake_awsglue_utils.getResolvedOptions = lambda _argv, _names: dict(glue_args)
    fake_awsglue.utils = fake_awsglue_utils
    monkeypatch.setitem(sys.modules, "awsglue", fake_awsglue)
    monkeypatch.setitem(sys.modules, "awsglue.utils", fake_awsglue_utils)

    from glue_jobs.bronze_to_silver import main as main_module

    captured = {}

    def fake_transform(*, spark, bronze_root_uri):
        captured["bronze_root_uri"] = bronze_root_uri
        return spark.createDataFrame([(2024,)], "_ingest_year SMALLINT")

    monkeypatch.setattr(chicago_crime, "transform", fake_transform)
    monkeypatch.setattr(main_module, "build_spark", lambda _name: spark)

    # Replace DataFrame.write with a fake that records the call shape so the
    # test never hits S3.
    class FakeWriter:
        def __init__(self):
            self.mode_value = None
            self.partition_cols = ()
            self.path = None

        def mode(self, m):
            self.mode_value = m
            return self

        def partitionBy(self, *cols):
            self.partition_cols = tuple(cols)
            return self

        def parquet(self, path):
            self.path = path

    fake_writer = FakeWriter()

    from pyspark.sql import DataFrame as PySparkDataFrame

    monkeypatch.setattr(
        PySparkDataFrame, "write", property(lambda _self: fake_writer)
    )

    main_module.main()

    assert captured["bronze_root_uri"] == "s3://test-bucket/raw"
    assert fake_writer.mode_value == "overwrite"
    assert fake_writer.partition_cols == ("_ingest_year",)
    assert fake_writer.path == "s3://test-bucket/standardized/chicago_crime/"
