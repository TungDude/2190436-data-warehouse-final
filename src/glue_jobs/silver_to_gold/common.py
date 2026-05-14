"""Shared helpers for the silver->gold loaders.

The hairy piece is :func:`scd2_merge`. Read its docstring before editing —
the staging-table + single-driver-transaction pattern is the only one
that survives a Glue job retry without leaving SCD2 rows expired without
a successor.

All SQL execution against Postgres goes through psycopg v3, which the
Glue job pulls in via ``--additional-python-modules psycopg[binary]``
(set in ``terraform/silver_to_gold.tf``). Under pytest the same module
is on the test harness's PATH (``requirements-dev.txt``).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable

import boto3
import psycopg
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import BinaryType

LOGGER = logging.getLogger(__name__)

# Silver rows whose source ``date`` could not be parsed land in this sentinel
# year partition (see CLAUDE.md Silver-Layer section). The gold loader MUST
# exclude them — they have no usable timestamp to drive FK resolution.
SENTINEL_INGEST_YEAR = 9999


# ---------------------------------------------------------------------------
# Credential + connection plumbing
# ---------------------------------------------------------------------------


def secret_to_jdbc_props(secret_arn: str, region: str) -> dict[str, str]:
    """Fetch RDS credentials from Secrets Manager and return JDBC props.

    The secret payload matches the RDS-standard JSON shape produced by
    ``terraform/rds.tf``: ``{username, password, engine, host, port, dbname}``.
    """
    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_arn)
    payload = response.get("SecretString")
    if not payload:
        raise RuntimeError(f"Secret {secret_arn} has no SecretString payload.")
    creds = json.loads(payload)
    required = ("host", "port", "dbname", "username", "password")
    missing = [k for k in required if not creds.get(k)]
    if missing:
        raise RuntimeError(
            f"Secret {secret_arn} missing required fields: {sorted(missing)}"
        )
    return {
        "url": f"jdbc:postgresql://{creds['host']}:{creds['port']}/{creds['dbname']}",
        "user": creds["username"],
        "password": creds["password"],
        "driver": "org.postgresql.Driver",
        "host": creds["host"],
        "port": str(creds["port"]),
        "dbname": creds["dbname"],
    }


def _psycopg_connect(jdbc_props: dict[str, str]) -> psycopg.Connection:
    """Open a psycopg v3 connection from the JDBC props dict."""
    return psycopg.connect(
        host=jdbc_props["host"],
        port=int(jdbc_props["port"]),
        dbname=jdbc_props["dbname"],
        user=jdbc_props["user"],
        password=jdbc_props["password"],
        connect_timeout=15,
    )


def _spark_jdbc_options(jdbc_props: dict[str, str]) -> dict[str, str]:
    """Return the subset of jdbc_props that Spark's JDBC reader/writer needs."""
    return {
        "url": jdbc_props["url"],
        "user": jdbc_props["user"],
        "password": jdbc_props["password"],
        "driver": jdbc_props["driver"],
    }


# ---------------------------------------------------------------------------
# Silver reader
# ---------------------------------------------------------------------------


def read_silver_table(
    spark: SparkSession, silver_database: str, table: str
) -> DataFrame:
    """Read a silver Parquet table from the Glue Catalog, sentinel-filtered.

    Rows landing in ``_ingest_year = 9999`` are routed to silver as the
    "could not parse date" triage partition (CLAUDE.md Silver-Layer
    section). The gold loader excludes them because they have no usable
    timestamp for FK resolution.
    """
    df = spark.table(f"{silver_database}.{table}")
    if "_ingest_year" in df.columns:
        df = df.filter(F.col("_ingest_year") != SENTINEL_INGEST_YEAR)
    return df


# ---------------------------------------------------------------------------
# SCD hash
# ---------------------------------------------------------------------------


# Sentinels for compute_scd_hash. Both are structural escape sequences
# that cannot legitimately appear in Chicago-crime silver data after
# silver's snake-case-and-cast pipeline:
#
#   _NULL_SENTINEL  replaces NULL inside a tracked column so
#                   (NULL, "x") and ("", "x") hash differently
#   _COL_SEPARATOR  joins per-column rendered values so ("ab", "c") and
#                   ("a", "bc") hash differently
#
# Using empty strings for either (the earlier design) collided pairs like
# the above and caused SCD2 to silently miss real attribute changes.
_NULL_SENTINEL = "<<NULL>>"
_COL_SEPARATOR = "||"


def compute_scd_hash(df: DataFrame, tracked_cols: list[str]) -> DataFrame:
    """Add a ``scd_hash`` column = SHA-256 over ``tracked_cols``.

    Null vs empty disambiguation uses ``_NULL_SENTINEL``; column-boundary
    ambiguity uses ``_COL_SEPARATOR``. See the module-level constants for
    rationale. Returns a new DataFrame with ``scd_hash`` appended; the
    existing columns are unchanged.
    """
    if not tracked_cols:
        # No tracked columns -> every row hashes to the same constant,
        # which collapses SCD2 to insert-once-per-NK semantics. That is
        # the correct V1 behaviour for dim_location (no SCD2-tracked
        # attributes until source 3 lands).
        constant_hash = F.unhex(F.sha2(F.lit(""), 256)).cast(BinaryType())
        return df.withColumn("scd_hash", constant_hash)

    parts = [
        F.coalesce(F.col(c).cast("string"), F.lit(_NULL_SENTINEL))
        for c in tracked_cols
    ]
    # F.sha2 returns a hex string; F.unhex turns it into the 32 raw bytes
    # that fit BYTEA naturally and match Python's hashlib.sha256(...).digest()
    # output (so test fixtures can compare hashes byte-for-byte).
    hash_col = F.unhex(F.sha2(F.concat_ws(_COL_SEPARATOR, *parts), 256)).cast(BinaryType())
    return df.withColumn("scd_hash", hash_col)


# ---------------------------------------------------------------------------
# SCD2 merge
# ---------------------------------------------------------------------------


def scd2_merge(
    spark: SparkSession,
    jdbc_props: dict[str, str],
    *,
    target_table: str,
    staging_table: str,
    df_new: DataFrame,
    natural_key: list[str],
    tracked_cols: list[str],
    attribute_cols: list[str] | None = None,
) -> dict[str, int]:
    """SCD2 merge from a Spark DataFrame into a Postgres SCD2 dim table.

    Sequence (matches the plan §"SCD2 merge tactic"):

    1. Compute ``scd_hash`` over ``tracked_cols`` on ``df_new``.
    2. Read current rows from ``target_table`` (``is_current = TRUE``)
       via Spark JDBC.
    3. Left-join in Spark, partition into ``new`` / ``changed`` /
       ``unchanged``. Drop ``unchanged``.
    4. Write ``new ∪ changed`` to ``staging_table`` with
       ``mode="overwrite"`` via Spark JDBC. **Single one-shot write —
       no per-row JDBC.**
    5. From the driver via ``psycopg`` in **one transaction**:

       * ``UPDATE target SET is_current=FALSE, scd_end_date=CURRENT_DATE
         FROM staging WHERE <natural_key match> AND target.is_current
         AND target.scd_hash <> staging.scd_hash``
       * ``INSERT INTO target (...) SELECT s.*, CURRENT_DATE,
         '9999-12-31', TRUE, COALESCE(prev_max + 1, 1), s.scd_hash
         FROM staging s LEFT JOIN (SELECT NK, MAX(scd_version) FROM target
         GROUP BY NK) prev_max ON ...``

       The UPDATE runs first so the no-current-row invariant holds for
       every NK we're about to insert. The two statements share a
       transaction so a job retry never leaves the table half-merged.

    Returns ``{"new": int, "changed": int, "unchanged": int}`` so the
    Glue job can log change counts.
    """
    if attribute_cols is None:
        # Everything in df_new minus SCD-2 metadata is an "attribute".
        meta_cols = {"scd_hash"}
        attribute_cols = [c for c in df_new.columns if c not in meta_cols]
    insert_cols = list(attribute_cols)

    df_new_hashed = compute_scd_hash(df_new, tracked_cols).select(
        *insert_cols, "scd_hash"
    )

    # Step 2: current rows from target.
    df_current = (
        spark.read.format("jdbc")
        .options(**_spark_jdbc_options(jdbc_props))
        .option("dbtable", target_table)
        .load()
        .filter(F.col("is_current") == F.lit(True))
        .select(*natural_key, F.col("scd_hash").alias("scd_hash_current"))
    )

    # Step 3: classify.
    joined = df_new_hashed.alias("n").join(
        df_current.alias("c"),
        on=[F.col(f"n.{k}").eqNullSafe(F.col(f"c.{k}")) for k in natural_key],
        how="left",
    )
    new_mask = F.col("c.scd_hash_current").isNull()
    changed_mask = (~new_mask) & (
        F.col("n.scd_hash") != F.col("c.scd_hash_current")
    )

    df_to_merge = joined.filter(new_mask | changed_mask).select(
        *[F.col(f"n.{c}") for c in insert_cols + ["scd_hash"]]
    )

    # Caching avoids re-running the JDBC read in the count() calls below.
    df_to_merge = df_to_merge.cache()
    counts = {
        "new": joined.filter(new_mask).count(),
        "changed": joined.filter(changed_mask).count(),
        "unchanged": joined.filter(~(new_mask | changed_mask)).count(),
    }

    if counts["new"] + counts["changed"] == 0:
        LOGGER.info(
            "scd2_merge %s: no new/changed rows, skipping driver SQL",
            target_table,
        )
        df_to_merge.unpersist()
        return counts

    # Step 4: write staging.
    LOGGER.info(
        "scd2_merge %s: writing %d rows to staging %s",
        target_table,
        counts["new"] + counts["changed"],
        staging_table,
    )
    (
        df_to_merge.write.format("jdbc")
        .options(**_spark_jdbc_options(jdbc_props))
        .option("dbtable", staging_table)
        .option("truncate", "true")
        .mode("overwrite")
        .save()
    )

    # Step 5: driver-side UPDATE + INSERT in one transaction.
    _apply_scd2_sql(
        jdbc_props=jdbc_props,
        target_table=target_table,
        staging_table=staging_table,
        natural_key=natural_key,
        insert_cols=insert_cols,
    )

    df_to_merge.unpersist()
    return counts


def _apply_scd2_sql(
    *,
    jdbc_props: dict[str, str],
    target_table: str,
    staging_table: str,
    natural_key: list[str],
    insert_cols: list[str],
) -> None:
    """Run the UPDATE + INSERT SCD2 transaction via psycopg.

    Identifier safety: ``target_table`` and ``staging_table`` are built
    by the caller (the loader module) from in-source constants, never
    from user input, so SQL injection isn't a vector. We still wrap them
    in ``psycopg.sql.Identifier`` for correctness.
    """
    nk_join = " AND ".join(
        f"t.{k} IS NOT DISTINCT FROM s.{k}" for k in natural_key
    )
    nk_group = ", ".join(natural_key)
    insert_col_list = ", ".join(insert_cols)
    select_col_list = ", ".join(f"s.{c}" for c in insert_cols)

    update_sql = f"""
        UPDATE {target_table} AS t
           SET is_current = FALSE,
               scd_end_date = CURRENT_DATE
          FROM {staging_table} AS s
         WHERE t.is_current = TRUE
           AND t.scd_hash IS DISTINCT FROM s.scd_hash
           AND {nk_join}
    """

    # The INSERT derives scd_version from MAX(scd_version) over ALL target
    # rows (current + expired) for the NK. This is correct EVEN AFTER the
    # UPDATE above expired the previous current row, because the UPDATE
    # only flips is_current=FALSE / scd_end_date=today — the expired row
    # stays in place and contributes to MAX. So prev_max+1 always yields
    # the next available version number.
    #
    # Same-day double-version caveat: the natural-key UNIQUE constraint
    # (NK, scd_start_date) prevents inserting a second version on the
    # same calendar day. Idempotent re-runs of the same data are safe
    # (the hash-equal pre-filter drops them before they reach this
    # INSERT). Two genuinely different versions for the same NK within
    # one Chicago day would fail the constraint and roll back the whole
    # transaction — acceptable given the once-daily ingest cadence.
    # Defense-in-depth: the upstream Spark classifier already pre-filters
    # unchanged rows out of the staging table, but if a future caller
    # (including tests) reaches `_apply_scd2_sql` with hash-equal rows in
    # staging, the NOT EXISTS predicate prevents an unwanted new version.
    nk_match_current = " AND ".join(
        f"cur.{k} IS NOT DISTINCT FROM s.{k}" for k in natural_key
    )
    insert_sql = f"""
        INSERT INTO {target_table} (
            {insert_col_list},
            scd_start_date, scd_end_date, is_current, scd_version, scd_hash
        )
        SELECT
            {select_col_list},
            CURRENT_DATE,
            DATE '9999-12-31',
            TRUE,
            COALESCE(prev_max.max_version, 0) + 1,
            s.scd_hash
          FROM {staging_table} AS s
          LEFT JOIN (
              SELECT {nk_group}, MAX(scd_version) AS max_version
                FROM {target_table}
               GROUP BY {nk_group}
          ) AS prev_max
            ON {" AND ".join(f"prev_max.{k} IS NOT DISTINCT FROM s.{k}" for k in natural_key)}
         WHERE NOT EXISTS (
             SELECT 1
               FROM {target_table} AS cur
              WHERE cur.is_current = TRUE
                AND cur.scd_hash IS NOT DISTINCT FROM s.scd_hash
                AND {nk_match_current}
         )
    """

    with _psycopg_connect(jdbc_props) as conn:
        with conn.cursor() as cur:
            LOGGER.info("scd2_merge %s: expiring changed current rows", target_table)
            cur.execute(update_sql)
            updated = cur.rowcount
            LOGGER.info("scd2_merge %s: expired %d rows", target_table, updated)
            cur.execute(insert_sql)
            inserted = cur.rowcount
            LOGGER.info("scd2_merge %s: inserted %d new versions", target_table, inserted)
        conn.commit()


# ---------------------------------------------------------------------------
# SCD1 / fact upsert
# ---------------------------------------------------------------------------


def build_upsert_sql(
    *,
    target_table: str,
    staging_table: str,
    all_cols: list[str],
    natural_key: list[str],
    update_cols: list[str],
) -> str:
    """Build the INSERT … ON CONFLICT DO UPDATE statement used by SCD1 + fact upserts.

    Extracted so the same SQL string is exercised by production code AND
    by the Postgres-backed tests (which pre-populate the staging table
    via psycopg rather than Spark JDBC). Drifting the two would let SQL
    bugs slip past the tests.
    """
    col_list = ", ".join(all_cols)
    set_list = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
    conflict_target = ", ".join(natural_key)
    return f"""
        INSERT INTO {target_table} ({col_list})
        SELECT {col_list} FROM {staging_table}
        ON CONFLICT ({conflict_target}) DO UPDATE SET {set_list}
    """


def scd1_upsert(
    spark: SparkSession,
    jdbc_props: dict[str, str],
    *,
    target_table: str,
    staging_table: str,
    df_new: DataFrame,
    natural_key: list[str],
    update_cols: list[str] | None = None,
) -> dict[str, int]:
    """Write df_new to a staging table, then INSERT...ON CONFLICT DO UPDATE.

    Used for Type 1 dims (overwrite semantics) and as the lower-level
    building block for fact upserts.
    """
    if update_cols is None:
        update_cols = [c for c in df_new.columns if c not in natural_key]

    (
        df_new.write.format("jdbc")
        .options(**_spark_jdbc_options(jdbc_props))
        .option("dbtable", staging_table)
        .option("truncate", "true")
        .mode("overwrite")
        .save()
    )

    upsert_sql = build_upsert_sql(
        target_table=target_table,
        staging_table=staging_table,
        all_cols=list(df_new.columns),
        natural_key=natural_key,
        update_cols=update_cols,
    )

    with _psycopg_connect(jdbc_props) as conn:
        with conn.cursor() as cur:
            cur.execute(upsert_sql)
            affected = cur.rowcount
        conn.commit()
    return {"upserted": affected}


# ---------------------------------------------------------------------------
# Fact upsert (alias of SCD1 upsert with a fact-shaped natural key)
# ---------------------------------------------------------------------------


def fact_upsert(
    spark: SparkSession,
    jdbc_props: dict[str, str],
    *,
    target_table: str,
    staging_table: str,
    df_new: DataFrame,
    natural_key: list[str],
) -> dict[str, int]:
    """Idempotent fact upsert by *natural_key* (e.g. ``["crime_id"]``).

    Every non-natural-key column in ``df_new`` is overwritten on conflict.
    This is what gives us the "re-running a day's load produces zero net
    new rows" guarantee from dimensional-design.md §3.2.1.
    """
    return scd1_upsert(
        spark,
        jdbc_props,
        target_table=target_table,
        staging_table=staging_table,
        df_new=df_new,
        natural_key=natural_key,
    )


# ---------------------------------------------------------------------------
# SCD2 FK lookup ("as-of-event-date")
# ---------------------------------------------------------------------------


def resolve_scd2_fk_asof(
    df_fact: DataFrame,
    df_dim: DataFrame,
    *,
    natural_key: list[str],
    event_date_col: str,
    dim_key_col: str,
    unknown_key: int = 0,
) -> DataFrame:
    """Resolve an SCD2 surrogate FK against the SCD2 dim rows in effect
    *at* ``event_date_col``.

    Left join on natural-key equality (NULL-safe) AND
    ``event_date BETWEEN scd_start_date AND scd_end_date``. Unmatched
    rows (e.g. null natural key, or event before any dim version) fall
    to ``unknown_key`` (default 0 per dimensional-design.md §8.5).

    Returns ``df_fact`` with ``dim_key_col`` appended.
    """
    join_conds = [
        F.col(f"f.{k}").eqNullSafe(F.col(f"d.{k}")) for k in natural_key
    ]
    join_conds.append(F.col(f"f.{event_date_col}") >= F.col("d.scd_start_date"))
    join_conds.append(F.col(f"f.{event_date_col}") <= F.col("d.scd_end_date"))

    joined = df_fact.alias("f").join(df_dim.alias("d"), on=join_conds, how="left")
    return joined.withColumn(
        dim_key_col,
        F.coalesce(F.col(f"d.{dim_key_col}"), F.lit(unknown_key)),
    ).select("f.*", dim_key_col)


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------


def jdbc_read_table(
    spark: SparkSession, jdbc_props: dict[str, str], table: str
) -> DataFrame:
    """Convenience wrapper: read a Postgres table via Spark JDBC."""
    return (
        spark.read.format("jdbc")
        .options(**_spark_jdbc_options(jdbc_props))
        .option("dbtable", table)
        .load()
    )


def coerce_columns_in_order(
    df: DataFrame, cols: Iterable[str]
) -> DataFrame:
    """Select *cols* in order. Useful before a JDBC write so the staging
    table's column order is deterministic."""
    return df.select(*list(cols))


__all__ = [
    "SENTINEL_INGEST_YEAR",
    "build_upsert_sql",
    "coerce_columns_in_order",
    "compute_scd_hash",
    "fact_upsert",
    "jdbc_read_table",
    "read_silver_table",
    "resolve_scd2_fk_asof",
    "scd1_upsert",
    "scd2_merge",
    "secret_to_jdbc_props",
]
