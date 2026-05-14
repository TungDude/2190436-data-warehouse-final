"""Postgres-backed tests for the SCD2 merge SQL.

Tests pre-populate a staging table via psycopg, then call
``common._apply_scd2_sql`` directly. This bypasses Spark JDBC writes
(which would need the Postgres driver JAR on the Spark classpath) and
focuses the verification on the SQL itself — the high-risk part.
"""

from __future__ import annotations

import hashlib
from datetime import date

import psycopg
import pytest

from glue_jobs.silver_to_gold import common


# ---------------------------------------------------------------------------
# Test fixtures and helpers
# ---------------------------------------------------------------------------


def _create_dim_crime_type_staging(conn: psycopg.Connection) -> None:
    """Create the SCD2 staging table for dim_crime_type."""
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE dw_staging.scd2_dim_crime_type_inflight (
                iucr            TEXT,
                primary_type    TEXT,
                description     TEXT,
                fbi_code        TEXT,
                scd_hash        BYTEA
            )
            """
        )
    conn.commit()


def _insert_into_staging(
    conn: psycopg.Connection, table: str, rows: list[tuple]
) -> None:
    with conn.cursor() as cur:
        placeholders = "(" + ", ".join("%s" for _ in rows[0]) + ")"
        cur.executemany(f"INSERT INTO {table} VALUES {placeholders}", rows)
    conn.commit()


def _hash(*parts: str | None) -> bytes:
    sentinel = common._NULL_SENTINEL
    separator = common._COL_SEPARATOR
    rendered = [p if p is not None else sentinel for p in parts]
    return hashlib.sha256(separator.join(rendered).encode()).digest()


def _read_dim_crime_type(conn: psycopg.Connection) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT iucr, primary_type, description, fbi_code, "
            "       scd_start_date, scd_end_date, is_current, scd_version "
            "  FROM dw.dim_crime_type "
            " WHERE crime_type_key <> 0 "
            " ORDER BY iucr, scd_version"
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Case A — new natural key inserts as is_current=TRUE, scd_version=1
# ---------------------------------------------------------------------------


def test_scd2_case_a_new_natural_key_inserts_v1(clean_dw, pg_conn):
    _create_dim_crime_type_staging(pg_conn)
    _insert_into_staging(
        pg_conn,
        "dw_staging.scd2_dim_crime_type_inflight",
        [("0820", "THEFT", "Under $500", "06", _hash("THEFT", "Under $500", "06"))],
    )
    common._apply_scd2_sql(
        jdbc_props=clean_dw,
        target_table="dw.dim_crime_type",
        staging_table="dw_staging.scd2_dim_crime_type_inflight",
        natural_key=["iucr"],
        insert_cols=["iucr", "primary_type", "description", "fbi_code"],
    )
    with psycopg.connect(
        host=clean_dw["host"],
        port=int(clean_dw["port"]),
        dbname=clean_dw["dbname"],
        user=clean_dw["user"],
        password=clean_dw["password"],
    ) as conn:
        rows = _read_dim_crime_type(conn)
    assert len(rows) == 1
    assert rows[0]["iucr"] == "0820"
    assert rows[0]["is_current"] is True
    assert rows[0]["scd_version"] == 1
    assert rows[0]["scd_start_date"] == date(1, 1, 1)


# ---------------------------------------------------------------------------
# Case B — empty staging is a no-op (re-run with nothing to merge)
# ---------------------------------------------------------------------------


def test_scd2_case_b_empty_staging_is_noop(clean_dw, pg_conn):
    """After an initial successful load, re-running the merge with an
    empty staging table must NOT touch any existing rows.

    The unchanged-hash-with-row-in-staging case is covered separately by
    ``test_scd2_unchanged_hash_in_staging_is_rejected_by_insert``.
    """
    _create_dim_crime_type_staging(pg_conn)
    _insert_into_staging(
        pg_conn,
        "dw_staging.scd2_dim_crime_type_inflight",
        [("0820", "THEFT", "Under $500", "06", _hash("THEFT", "Under $500", "06"))],
    )
    common._apply_scd2_sql(
        jdbc_props=clean_dw,
        target_table="dw.dim_crime_type",
        staging_table="dw_staging.scd2_dim_crime_type_inflight",
        natural_key=["iucr"],
        insert_cols=["iucr", "primary_type", "description", "fbi_code"],
    )

    # Empty staging — re-run must be a no-op.
    with pg_conn.cursor() as cur:
        cur.execute("TRUNCATE dw_staging.scd2_dim_crime_type_inflight")
    pg_conn.commit()

    common._apply_scd2_sql(
        jdbc_props=clean_dw,
        target_table="dw.dim_crime_type",
        staging_table="dw_staging.scd2_dim_crime_type_inflight",
        natural_key=["iucr"],
        insert_cols=["iucr", "primary_type", "description", "fbi_code"],
    )

    with psycopg.connect(
        host=clean_dw["host"],
        port=int(clean_dw["port"]),
        dbname=clean_dw["dbname"],
        user=clean_dw["user"],
        password=clean_dw["password"],
    ) as conn:
        rows = _read_dim_crime_type(conn)
    assert len(rows) == 1  # still just v1
    assert rows[0]["is_current"] is True


# ---------------------------------------------------------------------------
# Case C — same natural key, changed hash → expire v1, insert v2
# ---------------------------------------------------------------------------


def test_scd2_case_c_changed_hash_expires_and_inserts_v2(clean_dw, pg_conn):
    _create_dim_crime_type_staging(pg_conn)
    hash_v1 = _hash("THEFT", "Under $500", "06")
    hash_v2 = _hash("THEFT", "Under $750", "06")

    # Seed v1.
    _insert_into_staging(
        pg_conn,
        "dw_staging.scd2_dim_crime_type_inflight",
        [("0820", "THEFT", "Under $500", "06", hash_v1)],
    )
    common._apply_scd2_sql(
        jdbc_props=clean_dw,
        target_table="dw.dim_crime_type",
        staging_table="dw_staging.scd2_dim_crime_type_inflight",
        natural_key=["iucr"],
        insert_cols=["iucr", "primary_type", "description", "fbi_code"],
    )

    # Force v1's start_date back so the unique (iucr, scd_start_date)
    # constraint doesn't fire when v2 inserts today.
    with pg_conn.cursor() as cur:
        cur.execute(
            "UPDATE dw.dim_crime_type SET scd_start_date = DATE '2020-01-01' "
            "WHERE iucr = '0820' AND scd_version = 1"
        )
    pg_conn.commit()

    # Now stage v2.
    with pg_conn.cursor() as cur:
        cur.execute("TRUNCATE dw_staging.scd2_dim_crime_type_inflight")
    pg_conn.commit()
    _insert_into_staging(
        pg_conn,
        "dw_staging.scd2_dim_crime_type_inflight",
        [("0820", "THEFT", "Under $750", "06", hash_v2)],
    )

    common._apply_scd2_sql(
        jdbc_props=clean_dw,
        target_table="dw.dim_crime_type",
        staging_table="dw_staging.scd2_dim_crime_type_inflight",
        natural_key=["iucr"],
        insert_cols=["iucr", "primary_type", "description", "fbi_code"],
    )

    with psycopg.connect(
        host=clean_dw["host"],
        port=int(clean_dw["port"]),
        dbname=clean_dw["dbname"],
        user=clean_dw["user"],
        password=clean_dw["password"],
    ) as conn:
        rows = _read_dim_crime_type(conn)
    assert len(rows) == 2
    assert rows[0]["scd_version"] == 1
    assert rows[0]["is_current"] is False
    assert rows[1]["scd_version"] == 2
    assert rows[1]["is_current"] is True
    assert rows[1]["description"] == "Under $750"


# ---------------------------------------------------------------------------
# Defense-in-depth — staging row with unchanged hash must NOT insert a v2
#
# In production, the Spark classifier upstream filters unchanged rows
# before they reach the staging table. This test verifies the SQL itself
# has a guard against bug-induced regressions: if a future caller stages
# a hash-equal row, the NOT EXISTS predicate in the INSERT must skip it.
# ---------------------------------------------------------------------------


def test_scd2_unchanged_hash_in_staging_is_rejected_by_insert(clean_dw, pg_conn):
    _create_dim_crime_type_staging(pg_conn)
    same_hash = _hash("THEFT", "Under $500", "06")

    # Insert v1 directly so we can stage a deliberate duplicate.
    with pg_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO dw.dim_crime_type "
            "(iucr, primary_type, description, fbi_code, scd_start_date, "
            " scd_end_date, is_current, scd_version, scd_hash) VALUES "
            "('0820', 'THEFT', 'Under $500', '06', DATE '2020-01-01', "
            " DATE '9999-12-31', TRUE, 1, %s)",
            (same_hash,),
        )
    pg_conn.commit()

    # Stage the SAME hash — a buggy upstream might do this.
    _insert_into_staging(
        pg_conn,
        "dw_staging.scd2_dim_crime_type_inflight",
        [("0820", "THEFT", "Under $500", "06", same_hash)],
    )

    common._apply_scd2_sql(
        jdbc_props=clean_dw,
        target_table="dw.dim_crime_type",
        staging_table="dw_staging.scd2_dim_crime_type_inflight",
        natural_key=["iucr"],
        insert_cols=["iucr", "primary_type", "description", "fbi_code"],
    )

    with psycopg.connect(
        host=clean_dw["host"],
        port=int(clean_dw["port"]),
        dbname=clean_dw["dbname"],
        user=clean_dw["user"],
        password=clean_dw["password"],
    ) as conn:
        rows = _read_dim_crime_type(conn)
    assert len(rows) == 1
    assert rows[0]["scd_version"] == 1
    assert rows[0]["is_current"] is True


# ---------------------------------------------------------------------------
# Case D — pre-existing expired version + a new change keeps history
# ---------------------------------------------------------------------------


def test_scd2_case_d_third_version_preserves_prior_history(clean_dw, pg_conn):
    # Pre-seed two prior versions in the target.
    with pg_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO dw.dim_crime_type "
            "(iucr, primary_type, description, fbi_code, scd_start_date, "
            " scd_end_date, is_current, scd_version, scd_hash) VALUES "
            "('0820', 'THEFT', 'Under $300', '06', DATE '2018-01-01', "
            " DATE '2020-12-31', FALSE, 1, %s),"
            "('0820', 'THEFT', 'Under $500', '06', DATE '2021-01-01', "
            " DATE '2024-12-31', TRUE, 2, %s)",
            (_hash("THEFT", "Under $300", "06"), _hash("THEFT", "Under $500", "06")),
        )
    pg_conn.commit()

    _create_dim_crime_type_staging(pg_conn)
    hash_v3 = _hash("THEFT", "Under $750", "06")
    _insert_into_staging(
        pg_conn,
        "dw_staging.scd2_dim_crime_type_inflight",
        [("0820", "THEFT", "Under $750", "06", hash_v3)],
    )

    common._apply_scd2_sql(
        jdbc_props=clean_dw,
        target_table="dw.dim_crime_type",
        staging_table="dw_staging.scd2_dim_crime_type_inflight",
        natural_key=["iucr"],
        insert_cols=["iucr", "primary_type", "description", "fbi_code"],
    )

    with psycopg.connect(
        host=clean_dw["host"],
        port=int(clean_dw["port"]),
        dbname=clean_dw["dbname"],
        user=clean_dw["user"],
        password=clean_dw["password"],
    ) as conn:
        rows = _read_dim_crime_type(conn)
    assert len(rows) == 3
    versions = [(r["scd_version"], r["is_current"]) for r in rows]
    assert versions == [(1, False), (2, False), (3, True)]
    # v1 is untouched (was already expired)
    assert rows[0]["description"] == "Under $300"


# ---------------------------------------------------------------------------
# Reserved Unknown row protection — a NULL-NK stage row must NOT expire
# the seeded dim_location(0) Unknown row, even though the seed's all-NULL
# NK would IS-NOT-DISTINCT-FROM match it.
# ---------------------------------------------------------------------------


def _create_dim_location_staging(conn: psycopg.Connection) -> None:
    """Create the SCD2 staging table for dim_location. Column types
    mirror dw.dim_location in sql/dw_schema.sql §8.3.3."""
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE dw_staging.scd2_dim_location_inflight (
                community_area       SMALLINT,
                district             TEXT,
                ward                 SMALLINT,
                beat                 TEXT,
                block                TEXT,
                community_area_name  TEXT,
                scd_hash             BYTEA
            )
            """
        )
    conn.commit()


def test_scd2_null_nk_stage_row_does_not_expire_reserved_unknown(clean_dw, pg_conn):
    """Defense-in-depth for dimensional-design.md §8.5: a future loader
    bug that stages an all-NULL natural-key row must NEVER expire the
    seeded ``dim_location(0)`` reserved Unknown row.

    Without the ``scd_start_date <> '0001-01-01'`` guard in
    ``_apply_scd2_sql``, the UPDATE's ``IS NOT DISTINCT FROM`` predicate
    (NULL=NULL semantics) would match the seed and flip its
    ``is_current=FALSE``, breaking the Unknown-FK contract for every
    fact load.
    """
    _create_dim_location_staging(pg_conn)

    # Snapshot the seeded reserved row.
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT location_key, is_current, scd_version FROM dw.dim_location "
            "WHERE location_key = 0"
        )
        before = cur.fetchone()
    assert before == (0, True, 1), "seed precondition: dim_location(0) is current"

    # Stage a deliberate all-NULL NK row — represents a buggy upstream.
    with pg_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO dw_staging.scd2_dim_location_inflight "
            "(community_area, district, ward, beat, block, community_area_name, scd_hash) "
            "VALUES (NULL, NULL, NULL, NULL, NULL, NULL, %s)",
            (b"\x01" * 32,),  # any hash != reserved row's hash
        )
    pg_conn.commit()

    common._apply_scd2_sql(
        jdbc_props=clean_dw,
        target_table="dw.dim_location",
        staging_table="dw_staging.scd2_dim_location_inflight",
        natural_key=["community_area", "district", "ward", "beat"],
        insert_cols=[
            "community_area",
            "district",
            "ward",
            "beat",
            "block",
            "community_area_name",
        ],
    )

    # Reserved row untouched.
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT location_key, is_current, scd_version FROM dw.dim_location "
            "WHERE location_key = 0"
        )
        after = cur.fetchone()
    assert after == before, "reserved Unknown row must not be expired"

    # And the null-NK stage row must NOT have produced a new dim row.
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM dw.dim_location "
            "WHERE community_area IS NULL AND district IS NULL "
            "  AND ward IS NULL AND beat IS NULL AND location_key <> 0"
        )
        rogue_count = cur.fetchone()[0]
    assert rogue_count == 0, "null-NK stage row must not insert a new current row"
