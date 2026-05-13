"""Shared helpers for the bronze->silver source handlers.

Stdlib + pyspark only — no third-party deps so the same code runs locally
under PyPI ``pyspark==3.5.x`` and on Glue 5.0 without extra packaging.
"""

from __future__ import annotations

import re
from typing import Iterable

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window


_SNAKE_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")
_NON_ALPHANUM = re.compile(r"[^0-9a-zA-Z]+")


def to_snake_case(name: str) -> str:
    """Convert a column header to ``snake_case``.

    Idempotent — calling it on already-snake input returns the same string.
    Examples::

        "X Coordinate"  -> "x_coordinate"
        "FBI Code"      -> "fbi_code"
        "ID"            -> "id"
        "case_number"   -> "case_number"
    """
    spaced = _SNAKE_BOUNDARY.sub(r"\1_\2", name)
    cleaned = _NON_ALPHANUM.sub("_", spaced).strip("_").lower()
    return cleaned


def rename_columns_snake(df: DataFrame) -> DataFrame:
    """Apply :func:`to_snake_case` to every column of *df*."""
    renamed = df
    for old in df.columns:
        new = to_snake_case(old)
        if new != old:
            renamed = renamed.withColumnRenamed(old, new)
    return renamed


def parse_chicago_timestamp(col: Column) -> Column:
    """Parse Chicago Socrata's ``MM/dd/yyyy hh:mm:ss a`` strings to TIMESTAMP."""
    return F.to_timestamp(col, "MM/dd/yyyy hh:mm:ss a")


def cast_bool_yn(col: Column) -> Column:
    """Cast Socrata-style ``"true"``/``"false"`` strings to BOOLEAN.

    Garbage input (empty string, unknown literals) becomes ``NULL`` rather
    than raising — bronze is "warts and all" and silver triages, never
    refuses, malformed boolean inputs.
    """
    lowered = F.lower(F.trim(col))
    return (
        F.when(lowered == F.lit("true"), F.lit(True))
        .when(lowered == F.lit("false"), F.lit(False))
        .otherwise(F.lit(None).cast("boolean"))
    )


def dedup_latest(
    df: DataFrame,
    key_cols: Iterable[str],
    order_cols: Iterable[Column],
) -> DataFrame:
    """Keep one row per *key_cols* combination, ordered by *order_cols* desc.

    *order_cols* must already encode the desired direction
    (``F.col("updated_on").desc_nulls_last()``). The first row in that order
    survives; the rest are dropped.
    """
    key_cols = list(key_cols)
    order_cols = list(order_cols)

    # Reserved helper column name; prefixed and suffixed to minimise the
    # chance of colliding with a real source column. We still fail loudly if
    # a source ever introduces a column with this exact name, because a
    # silent overwrite would corrupt dedup ranks.
    helper = "__dedup_rn__"
    if helper in df.columns:
        raise ValueError(
            f"dedup_latest helper column name '{helper}' collides with an "
            f"existing source column. Rename the source column or update "
            f"common.dedup_latest's helper constant."
        )
    window = Window.partitionBy(*key_cols).orderBy(*order_cols)
    ranked = df.withColumn(helper, F.row_number().over(window))
    return ranked.where(F.col(helper) == 1).drop(helper)
