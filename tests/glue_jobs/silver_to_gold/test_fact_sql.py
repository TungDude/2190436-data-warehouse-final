"""Postgres-backed tests for fact_crime upsert idempotency.

Same isolation pattern as test_scd2_sql.py — pre-populates the staging
table via psycopg and calls a wrapper around the ON CONFLICT INSERT
SQL that ``fact_upsert`` issues, without going through Spark's JDBC
writer.
"""

from __future__ import annotations

import psycopg
import pytest

from glue_jobs.silver_to_gold.facts import chicago_crime as fact_loader


FACT_COLS = fact_loader.FACT_COLS


def _create_fact_staging(conn: psycopg.Connection) -> None:
    """Create the fact_crime staging table with the same column shape."""
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE dw_staging.fact_crime_inflight (
                crime_id              BIGINT,
                case_number           TEXT,
                occurrence_date_key   INTEGER,
                occurrence_time_key   SMALLINT,
                report_date_key       INTEGER,
                location_key          BIGINT,
                crime_type_key        BIGINT,
                weather_key           BIGINT,
                flags_key             SMALLINT,
                incident_count        SMALLINT,
                is_arrest             SMALLINT,
                is_domestic           SMALLINT,
                hours_to_update       INTEGER,
                latitude              NUMERIC(9,6),
                longitude             NUMERIC(9,6),
                temperature_celsius   NUMERIC(5,2),
                precipitation_mm      NUMERIC(6,2)
            )
            """
        )
    conn.commit()


def _stage_row(conn: psycopg.Connection, **overrides) -> None:
    """Insert one row into fact_crime staging with sensible defaults.

    The defaults reference only seeded surrogate keys (date 0/20240101,
    time 0, location 0 Unknown, crime_type 0 Unknown, weather -1
    Unavailable, flags 1 No-Arrest-Non-Domestic).
    """
    defaults = {
        "crime_id": 1,
        "case_number": "JE000001",
        "occurrence_date_key": 20240101,
        "occurrence_time_key": 0,
        "report_date_key": 20240101,
        "location_key": 0,
        "crime_type_key": 0,
        "weather_key": -1,
        "flags_key": 1,
        "incident_count": 1,
        "is_arrest": 0,
        "is_domestic": 0,
        "hours_to_update": 24,
        "latitude": None,
        "longitude": None,
        "temperature_celsius": None,
        "precipitation_mm": None,
    }
    defaults.update(overrides)
    values = [defaults[c] for c in FACT_COLS]
    placeholders = ", ".join("%s" for _ in FACT_COLS)
    cols = ", ".join(FACT_COLS)
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO dw_staging.fact_crime_inflight ({cols}) "
            f"VALUES ({placeholders})",
            values,
        )
    conn.commit()


def _apply_fact_upsert(jdbc_props):
    """Run the same INSERT ... ON CONFLICT DO UPDATE that fact_upsert issues.

    Uses common.build_upsert_sql so test and production share one SQL
    generator; drift between the two would otherwise let bugs slip past.
    """
    from glue_jobs.silver_to_gold import common

    sql = common.build_upsert_sql(
        target_table="dw.fact_crime",
        staging_table="dw_staging.fact_crime_inflight",
        all_cols=FACT_COLS,
        natural_key=["crime_id"],
        update_cols=[c for c in FACT_COLS if c != "crime_id"],
    )
    with psycopg.connect(
        host=jdbc_props["host"],
        port=int(jdbc_props["port"]),
        dbname=jdbc_props["dbname"],
        user=jdbc_props["user"],
        password=jdbc_props["password"],
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            affected = cur.rowcount
        conn.commit()
    return affected


def _count_fact_crime(jdbc_props) -> int:
    with psycopg.connect(
        host=jdbc_props["host"],
        port=int(jdbc_props["port"]),
        dbname=jdbc_props["dbname"],
        user=jdbc_props["user"],
        password=jdbc_props["password"],
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM dw.fact_crime")
            return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_fact_upsert_inserts_new_row(clean_dw, pg_conn):
    _create_fact_staging(pg_conn)
    _stage_row(pg_conn, crime_id=100)
    _apply_fact_upsert(clean_dw)
    assert _count_fact_crime(clean_dw) == 1


def test_fact_upsert_is_idempotent_by_crime_id(clean_dw, pg_conn):
    """Loading the same staging row twice produces exactly one fact row."""
    _create_fact_staging(pg_conn)
    _stage_row(pg_conn, crime_id=100)
    _apply_fact_upsert(clean_dw)
    first_count = _count_fact_crime(clean_dw)

    # Re-stage the same row and re-apply.
    with pg_conn.cursor() as cur:
        cur.execute("TRUNCATE dw_staging.fact_crime_inflight")
    pg_conn.commit()
    _stage_row(pg_conn, crime_id=100, is_arrest=1)  # tweak a measure
    _apply_fact_upsert(clean_dw)

    second_count = _count_fact_crime(clean_dw)
    assert first_count == second_count == 1

    # Verify the UPDATE took effect: is_arrest should now be 1.
    with psycopg.connect(
        host=clean_dw["host"],
        port=int(clean_dw["port"]),
        dbname=clean_dw["dbname"],
        user=clean_dw["user"],
        password=clean_dw["password"],
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT is_arrest FROM dw.fact_crime WHERE crime_id = 100"
            )
            assert cur.fetchone()[0] == 1


def test_fact_upsert_preserves_crime_pk_across_reruns(clean_dw, pg_conn):
    """Re-running the same load must not bump crime_pk (the surrogate)."""
    _create_fact_staging(pg_conn)
    _stage_row(pg_conn, crime_id=100)
    _apply_fact_upsert(clean_dw)

    with psycopg.connect(
        host=clean_dw["host"],
        port=int(clean_dw["port"]),
        dbname=clean_dw["dbname"],
        user=clean_dw["user"],
        password=clean_dw["password"],
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT crime_pk FROM dw.fact_crime WHERE crime_id = 100"
            )
            pk_first = cur.fetchone()[0]

    with pg_conn.cursor() as cur:
        cur.execute("TRUNCATE dw_staging.fact_crime_inflight")
    pg_conn.commit()
    _stage_row(pg_conn, crime_id=100, case_number="JE000999")
    _apply_fact_upsert(clean_dw)

    with psycopg.connect(
        host=clean_dw["host"],
        port=int(clean_dw["port"]),
        dbname=clean_dw["dbname"],
        user=clean_dw["user"],
        password=clean_dw["password"],
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT crime_pk, case_number FROM dw.fact_crime WHERE crime_id = 100"
            )
            pk_second, case_number = cur.fetchone()

    assert pk_first == pk_second
    assert case_number == "JE000999"


def test_fact_upsert_resolves_null_fks_to_unknown_surrogates(clean_dw, pg_conn):
    """A row referencing only Unknown surrogates (loc=0, type=0, weather=-1,
    flags=0) inserts cleanly — the FK constraints are satisfied by the
    reserved rows seeded in dw_seed.sql."""
    _create_fact_staging(pg_conn)
    _stage_row(
        pg_conn,
        crime_id=200,
        location_key=0,
        crime_type_key=0,
        weather_key=-1,
        flags_key=0,
    )
    _apply_fact_upsert(clean_dw)
    assert _count_fact_crime(clean_dw) == 1


def test_fact_upsert_with_dim_date_unknown_inserts_cleanly(clean_dw, pg_conn):
    """A fact whose occurrence_date_key=0 (Unknown date — pre-2018 or
    unparseable) must insert cleanly against dim_date(0), not be dropped.

    This guards the documented "1990 occurrence -> dim_date_key=0"
    behaviour from Track 4's risk review (the prior plan's claim that
    1990 resolves to a valid dim_date is wrong; the loader falls to
    dim_date(0) when the smart key is outside the seeded range, which
    in practice happens for any year < 2018).
    """
    _create_fact_staging(pg_conn)
    _stage_row(
        pg_conn,
        crime_id=400,
        occurrence_date_key=0,
        report_date_key=0,
    )
    _apply_fact_upsert(clean_dw)

    with psycopg.connect(
        host=clean_dw["host"],
        port=int(clean_dw["port"]),
        dbname=clean_dw["dbname"],
        user=clean_dw["user"],
        password=clean_dw["password"],
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT dd.day_name "
                "  FROM dw.fact_crime fc "
                "  JOIN dw.dim_date dd ON dd.date_key = fc.occurrence_date_key "
                " WHERE fc.crime_id = 400"
            )
            row = cur.fetchone()
    assert row is not None
    assert row[0] == "Unknown"  # the dim_date(0) Unknown row's day_name


def test_fact_crime_fact_cols_order_matches_ddl(clean_dw, pg_conn):
    """Sanity-check that fact_crime.FACT_COLS lines up with dw.fact_crime
    column order (excluding the IDENTITY crime_pk). Any drift here would
    fail the JDBC write at runtime."""
    _create_fact_staging(pg_conn)
    _stage_row(pg_conn, crime_id=300)
    _apply_fact_upsert(clean_dw)

    with psycopg.connect(
        host=clean_dw["host"],
        port=int(clean_dw["port"]),
        dbname=clean_dw["dbname"],
        user=clean_dw["user"],
        password=clean_dw["password"],
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'dw' AND table_name = 'fact_crime' "
                "  AND column_name <> 'crime_pk' "
                "ORDER BY ordinal_position"
            )
            db_cols = [r[0] for r in cur.fetchall()]
    assert db_cols == FACT_COLS
