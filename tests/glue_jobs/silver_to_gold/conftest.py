"""Pytest fixtures for silver -> gold tests.

Two test surfaces:

* **Spark-only** — `test_common.py`. Synthetic DataFrames; no Postgres.
  Exercises `compute_scd_hash`, `read_silver_table`, `resolve_scd2_fk_asof`.

* **Postgres-backed** — `test_scd_sql.py`, `test_fact_sql.py`. A real
  Postgres 16 container (testcontainers) is initialised once per
  session with `sql/dw_schema.sql` + `sql/dw_seed.sql`. Tests pre-
  populate staging tables via psycopg, call the SQL generators from
  `common.py` (the `_apply_scd2_sql` / fact upsert helpers), then
  assert against the target tables. This decouples the merge SQL
  correctness from Spark's JDBC writer (which would require the
  Postgres driver JAR on the Spark classpath).

The container only starts when one of the Postgres fixtures is
requested by a test, so the Spark-only file path stays Docker-free.
"""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest

# testcontainers + Docker are required for the Postgres-backed tests. We
# gracefully degrade if either is missing: tests that request the
# postgres_container fixture skip with a clear message; Spark-only tests
# in test_common.py keep working.
try:
    from testcontainers.postgres import PostgresContainer
    _TC_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on host env
    PostgresContainer = None  # type: ignore[assignment]
    _TC_AVAILABLE = False


def _docker_available() -> bool:
    if not _TC_AVAILABLE:
        return False
    try:
        import docker  # noqa: PLC0415
    except ImportError:
        return False
    try:
        docker.from_env().ping()
        return True
    except Exception:  # noqa: BLE001 - any docker-side error means unavailable
        return False


_REQUIRES_PG_REASON = (
    "Postgres-backed silver->gold tests need testcontainers + a reachable "
    "Docker daemon. Install with `pip install -r requirements-dev.txt` and "
    "ensure Docker is running."
)


REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_SQL = REPO_ROOT / "sql" / "dw_schema.sql"
SEED_SQL = REPO_ROOT / "sql" / "dw_seed.sql"


@pytest.fixture(scope="session")
def postgres_container():
    """Session-scoped Postgres 16 container, initialised with dw_schema + dw_seed.

    Skips at fixture level if Docker / testcontainers aren't available so
    Spark-only tests in test_common.py keep running on Docker-less hosts.
    """
    if not _docker_available():
        pytest.skip(_REQUIRES_PG_REASON)
    container = PostgresContainer("postgres:16", username="test", password="test", dbname="dw")
    container.start()
    try:
        _apply_sql_file(container, SCHEMA_SQL)
        _apply_sql_file(container, SEED_SQL)
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def jdbc_props(postgres_container) -> dict[str, str]:
    """common.py-shaped JDBC props for the test container."""
    host = postgres_container.get_container_host_ip()
    port = postgres_container.get_exposed_port(5432)
    return {
        "url": f"jdbc:postgresql://{host}:{port}/dw",
        "user": "test",
        "password": "test",
        "driver": "org.postgresql.Driver",
        "host": host,
        "port": str(port),
        "dbname": "dw",
    }


@pytest.fixture()
def clean_dw(jdbc_props):
    """Truncate transactional + SCD2 dim tables before each test.

    The seeded SCD0 / junk rows (dim_date 4748 + dim_time_of_day 24 +
    dim_crime_flags 5 + reserved Unknown rows) are preserved; only data
    the silver -> gold loaders write is cleared between tests.
    """
    with psycopg.connect(**_pg_kwargs(jdbc_props)) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE dw.fact_crime CASCADE")
            cur.execute("DELETE FROM dw.dim_location WHERE location_key <> 0")
            cur.execute("DELETE FROM dw.dim_crime_type WHERE crime_type_key <> 0")
            cur.execute("DROP TABLE IF EXISTS dw_staging.scd2_dim_location_inflight")
            cur.execute("DROP TABLE IF EXISTS dw_staging.scd2_dim_crime_type_inflight")
            cur.execute("DROP TABLE IF EXISTS dw_staging.fact_crime_inflight")
        conn.commit()
    yield jdbc_props


@pytest.fixture()
def pg_conn(jdbc_props):
    """Open a psycopg connection to the container."""
    with psycopg.connect(**_pg_kwargs(jdbc_props)) as conn:
        yield conn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _apply_sql_file(container: PostgresContainer, path: Path) -> None:
    conn_kwargs = {
        "host": container.get_container_host_ip(),
        "port": container.get_exposed_port(5432),
        "dbname": "dw",
        "user": "test",
        "password": "test",
    }
    sql_text = path.read_text()
    with psycopg.connect(**conn_kwargs) as conn:
        with conn.cursor() as cur:
            cur.execute(sql_text)
        conn.commit()


def _pg_kwargs(jdbc_props: dict[str, str]) -> dict:
    return {
        "host": jdbc_props["host"],
        "port": int(jdbc_props["port"]),
        "dbname": jdbc_props["dbname"],
        "user": jdbc_props["user"],
        "password": jdbc_props["password"],
    }
