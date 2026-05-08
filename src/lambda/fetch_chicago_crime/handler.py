import csv
import io
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import boto3


S3_CLIENT = boto3.client("s3")


def lambda_handler(event, context):
    event = event or {}

    bucket = require_env("RAW_BUCKET")
    prefix = require_env("RAW_PREFIX").strip("/")
    api_url = require_env("CHICAGO_CRIME_API_URL")
    source_timezone = ZoneInfo(os.getenv("SOURCE_TIMEZONE", "America/Chicago"))
    fetch_limit = int(os.getenv("FETCH_LIMIT", "50000"))
    lookback_days = int(os.getenv("FETCH_LOOKBACK_DAYS", "8"))

    start_date, end_date = resolve_date_range(event, source_timezone, lookback_days)
    ingest_time = datetime.now(timezone.utc)
    ingest_date = ingest_time.date().isoformat()

    csv_body, request_url = fetch_chicago_crime_csv(
        api_url=api_url,
        start_date=start_date,
        end_date=end_date,
        fetch_limit=fetch_limit,
    )
    row_count = count_csv_rows(csv_body)
    source_range = format_source_range(start_date, end_date)

    object_key = (
        f"{prefix}/ingest_date={ingest_date}/"
        f"chicago_crime_{source_range}_"
        f"{ingest_time.strftime('%Y%m%dT%H%M%SZ')}.csv"
    )

    S3_CLIENT.put_object(
        Bucket=bucket,
        Key=object_key,
        Body=csv_body.encode("utf-8"),
        ContentType="text/csv",
        Metadata={
            "source": "city-of-chicago-crimes",
            "start-date": start_date.isoformat(),
            "end-date": end_date.isoformat(),
            "ingest-time-utc": ingest_time.isoformat(),
            "request-url": request_url[:2000],
            "row-count": str(row_count),
        },
    )

    result = {
        "bucket": bucket,
        "key": object_key,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "ingest_date": ingest_date,
        "row_count": row_count,
    }
    print(json.dumps(result))
    return result


def require_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def resolve_date_range(event, source_timezone, lookback_days):
    if "start_date" in event or "end_date" in event:
        if "start_date" not in event or "end_date" not in event:
            raise ValueError("Both start_date and end_date are required for range fetches.")

        start_date = parse_date(event["start_date"])
        end_date = parse_date(event["end_date"])
        if end_date < start_date:
            raise ValueError("end_date must be on or after start_date.")
        return start_date, end_date

    if "target_date" in event:
        target_date = parse_date(event["target_date"])
        return target_date, target_date

    source_now = datetime.now(source_timezone)
    target_date = source_now.date() - timedelta(days=lookback_days)
    return target_date, target_date


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def format_source_range(start_date, end_date):
    if start_date == end_date:
        return start_date.isoformat()
    return f"{start_date.isoformat()}_to_{end_date.isoformat()}"


def fetch_chicago_crime_csv(api_url, start_date, end_date, fetch_limit):
    start = datetime.combine(start_date, datetime.min.time())
    exclusive_end = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

    params = {
        "$limit": str(fetch_limit),
        "$order": "date",
        "$where": (
            f"date >= '{start.strftime('%Y-%m-%dT%H:%M:%S')}' "
            f"AND date < '{exclusive_end.strftime('%Y-%m-%dT%H:%M:%S')}'"
        ),
    }

    request_url = f"{api_url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        request_url,
        headers={
            "Accept": "text/csv",
            "User-Agent": "data-warehouse-final-fetcher/1.0",
        },
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read().decode("utf-8")

    return body, request_url


def count_csv_rows(csv_body):
    reader = csv.reader(io.StringIO(csv_body))
    row_count = sum(1 for _ in reader)
    return max(row_count - 1, 0)
