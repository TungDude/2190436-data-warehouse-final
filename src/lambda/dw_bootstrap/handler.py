"""One-shot DDL bootstrap Lambda for the warehouse RDS instance.

Invoked by Terraform via aws_lambda_invocation when the SQL files change
(filemd5 trigger). Reads dw_schema.sql and dw_seed.sql from S3 and applies
them to RDS in two separate transactions: schema first, then seed.

Both SQL scripts are idempotent (CREATE ... IF NOT EXISTS and
INSERT ... ON CONFLICT DO NOTHING) so re-invocations are safe and produce
no net change after the first successful run.
"""

from __future__ import annotations

import json
import logging
import os
import time

import boto3
import psycopg

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

S3_CLIENT = boto3.client("s3")
SECRETS_CLIENT = boto3.client("secretsmanager")


def lambda_handler(event, context):  # noqa: ARG001
    """Run the schema and seed SQL files against the warehouse RDS instance.

    Returns a JSON-serialisable dict with elapsed milliseconds for each
    script. Raises on failure so Terraform's aws_lambda_invocation surfaces
    the error in the apply log.
    """
    secret_arn = _require_env("SECRET_ARN")
    bucket = _require_env("BUCKET")
    schema_key = _require_env("SCHEMA_KEY")
    seed_key = _require_env("SEED_KEY")

    schema_sql = _fetch_s3_text(bucket, schema_key)
    seed_sql = _fetch_s3_text(bucket, seed_key)
    creds = _fetch_db_credentials(secret_arn)

    conn_kwargs = {
        "host": creds["host"],
        "port": int(creds["port"]),
        "dbname": creds["dbname"],
        "user": creds["username"],
        "password": creds["password"],
        "connect_timeout": 15,
    }

    schema_ms = _run_sql_file(conn_kwargs, schema_sql, label="schema")
    seed_ms = _run_sql_file(conn_kwargs, seed_sql, label="seed")

    result = {
        "status": "ok",
        "schema_ms": schema_ms,
        "seed_ms": seed_ms,
        "schema_bytes": len(schema_sql),
        "seed_bytes": len(seed_sql),
    }
    LOGGER.info("dw_bootstrap complete: %s", json.dumps(result))
    return result


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _fetch_s3_text(bucket: str, key: str) -> str:
    obj = S3_CLIENT.get_object(Bucket=bucket, Key=key)
    body = obj["Body"].read()
    return body.decode("utf-8")


def _fetch_db_credentials(secret_arn: str) -> dict[str, str]:
    response = SECRETS_CLIENT.get_secret_value(SecretId=secret_arn)
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
    return creds


def _run_sql_file(conn_kwargs: dict, sql_text: str, *, label: str) -> int:
    """Execute one SQL file in its own transaction. Returns elapsed ms."""
    started = time.monotonic()
    LOGGER.info("dw_bootstrap %s: opening connection", label)
    with psycopg.connect(**conn_kwargs) as conn:
        with conn.cursor() as cur:
            cur.execute(sql_text)
        conn.commit()
    elapsed_ms = int((time.monotonic() - started) * 1000)
    LOGGER.info("dw_bootstrap %s: applied in %d ms", label, elapsed_ms)
    return elapsed_ms
