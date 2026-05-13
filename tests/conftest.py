"""Pytest fixtures shared across the bronze->silver test modules."""

from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

# Pin the JVM/process timezone *before* pyspark imports. PySpark materialises
# Spark TIMESTAMP -> Python datetime through the JVM's default TimeZone, which
# is read from the ``TZ`` env var at JVM startup. Without this pin the
# timestamp assertions are flaky on developer machines whose system TZ differs
# from the source data's TZ (the chicago_crime feed is America/Chicago).
os.environ["TZ"] = "America/Chicago"
if hasattr(time, "tzset"):  # POSIX only; Spark's local mode is POSIX-only too.
    time.tzset()

# Pin Spark's Python interpreter to the one running these tests. Without this,
# Spark workers spawn via system `python3`, which on Nix dev shells is often a
# different minor version than the venv driver — PySpark refuses to run with
# mismatched minor versions ([PYTHON_VERSION_MISMATCH]).
os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)

import pytest  # noqa: E402

# ``src/`` is on sys.path via ``[tool.pytest.ini_options].pythonpath`` in
# pyproject.toml — no runtime sys.path mutation needed here.
ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def spark():
    """Session-scoped local SparkSession pinned to the chicago_crime timezone."""
    from pyspark.sql import SparkSession

    builder = (
        SparkSession.builder.appName("bronze_to_silver-tests")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.sql.session.timeZone", "America/Chicago")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        # Reinforce JVM-side timezone via Spark driver/executor extra Java
        # options so a pre-existing JVM doesn't ignore the env var.
        .config("spark.driver.extraJavaOptions", "-Duser.timezone=America/Chicago")
        .config("spark.executor.extraJavaOptions", "-Duser.timezone=America/Chicago")
    )
    session = builder.getOrCreate()
    session.sparkContext.setLogLevel("WARN")
    yield session
    session.stop()


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return ROOT / "tests" / "fixtures"


@pytest.fixture()
def empty_bronze_root(tmp_path: Path) -> Path:
    """An empty ``raw/`` root used to test the empty-input fast path."""
    raw_root = tmp_path / "raw"
    (raw_root / "chicaho_crime").mkdir(parents=True)
    return tmp_path


@pytest.fixture()
def isolated_bronze_root(tmp_path: Path, fixtures_dir: Path) -> Path:
    """Copy the chicago_crime fixture into a transient tmp ``raw/`` root."""
    raw_root = tmp_path / "raw"
    src = fixtures_dir / "chicago_crime"
    dst = raw_root / "chicaho_crime"
    shutil.copytree(src, dst)
    return tmp_path
