# Data Warehouse Project Instructions

This repository is for a data warehouse project using Chicago crime data as the
main fact source, with lookup, socioeconomic, weather, and optional arrest data
as enrichment sources.

## Local Configuration

Before running AWS commands, deployment scripts, or infrastructure code:

1. Check for `.agents/AGENTS.local.md`.
2. If it exists and points to another file, read that target file.
3. Otherwise, check for `.claude/CLAUDE.local.md`.
4. Use the AWS local profile declared there.
5. If neither local file exists, or the file does not declare an AWS profile,
   stop and prompt the user to create either `.claude/CLAUDE.local.md` or
   `.agents/AGENTS.local.md`.

Do not guess an AWS profile, do not use `default` unless the local config says
so, and do not add credentials or secrets to tracked files. Local configuration
files are intended to stay gitignored.

The local config should contain a clear AWS profile entry, for example:

```md
# Local Configuration (gitignored)

## AWS Local Profile

- data-warehouse-final
```

## Course Lecture Reference

This project is graded against material taught in two Chulalongkorn courses
(2190436 Data Warehousing and 2190518 Data Engineering and Big Data). The
lecture slides have been transcribed to markdown under `docs/lectures/`.

Whenever a task touches a concept that was taught in class — dimensional
modeling, SCDs, fact-table types, conformed dimensions, big-data
architectures, NoSQL choices, Spark, Airflow, Kafka, etc. — read
`docs/lectures/INDEX.md` first to find the right lecture, then read the
specific lecture markdown(s) it points to. Do not grep the lecture
directory blindly; the index is the entry point.

The PDF originals remain in `slides/midterm/` and `slides/final/` and are
the authoritative source if the markdown extraction is ambiguous.

## Project Goal

Build a dimensional model and data pipeline that can ingest multiple data
sources, stage raw data in a data lake, transform it into warehouse tables, and
support analytics on crime trends by time, location, crime type, weather, and
community characteristics.

Use the 2018-2024 slice of Chicago crime data unless a task explicitly asks for
a different date range. This keeps the project large enough for the big-data
requirement while remaining practical to process.

## Tooling Prerequisites

This project uses Terraform to provision and manage AWS infrastructure. Terraform
and the AWS CLI are required for infrastructure and deployment work.

Before running infrastructure tasks, verify:

- Terraform is installed and available as `terraform`.
- AWS CLI is installed and available as `aws`.
- The AWS profile is configured in `.agents/AGENTS.local.md` or
  `.claude/CLAUDE.local.md` as described in the Local Configuration section.

## Target Dimensional Model

Recommended warehouse tables:

| Table | Purpose |
|---|---|
| `fact_crime` | One row per crime incident. Main measures and event flags. |
| `dim_time` | Calendar and hour attributes derived from crime timestamps. |
| `dim_location` | Community area, district, ward, beat, and optional SCD2 socioeconomic attributes. |
| `dim_crime_type` | IUCR, primary type, description, FBI code, and index classification. |
| `dim_weather` | Hourly weather observations joined by date and hour. |
| `dim_arrestee` or arrest bridge | Optional arrest enrichment if arrest records are included. |

Fact grain:

- `fact_crime` should stay at the individual crime incident grain.
- Use `ID` from the Chicago crime source as the stable source key.
- Join weather at date-hour grain.
- Join location by community area, district, ward, and beat where available.

## Data Sources

### 1. Chicago Crime Reports

Main fact table source.

| Field | Value |
|---|---|
| Source | City of Chicago Official Data Portal |
| Format | CSV |
| Size | ~8 million rows from 2001-present, updated daily |
| Project slice | 2018-2024, approximately 1.5 million rows |
| Portal | https://data.cityofchicago.org/Public-Safety/Crimes-2001-to-Present/ijzp-q8t2 |
| API CSV | `https://data.cityofchicago.org/resource/ijzp-q8t2.csv?$where=year >= 2018&$limit=2000000` |
| Kaggle mirror | https://www.kaggle.com/datasets/adelanseur/crimes-2001-to-present-chicago |

This dataset reflects reported crime incidents extracted from the Chicago Police
Department CLEAR system. The official portal excludes the most recent seven
days.

Important mappings:

| Source column | Warehouse mapping |
|---|---|
| `ID` | `fact_crime.crime_id` source key |
| `Date` | `dim_time` and weather date-hour join |
| `Primary Type` | `dim_crime_type` |
| `Description` | `dim_crime_type` |
| `IUCR` | `dim_crime_type` lookup key |
| `FBI Code` | `dim_crime_type` |
| `Community Area` | `dim_location` |
| `District`, `Ward`, `Beat` | `dim_location` |
| `Arrest` | `fact_crime` boolean |
| `Domestic` | `fact_crime` boolean |
| `Latitude`, `Longitude` | `fact_crime` coordinates or degenerate location attributes |

### 2. IUCR Crime Codes

Crime classification dimension lookup.

| Field | Value |
|---|---|
| Source | Chicago Data Portal |
| Format | CSV |
| Size | ~400 rows |
| Portal | https://data.cityofchicago.org/Public-Safety/Chicago-Police-Department-Illinois-Uniform-Crime-R/c7ck-438e |

IUCR codes are four-digit law-enforcement classification codes. Use this source
to enrich `dim_crime_type` with FBI code, index/non-index classification, and
offense category.

### 3. Chicago Community Area Socioeconomic Data

Location enrichment and SCD Type 2 candidate.

| Field | Value |
|---|---|
| Source | City of Chicago Data Portal |
| Format | CSV |
| Size | 77 rows, one per community area |
| Portal | https://data.cityofchicago.org/Health-Human-Services/Census-Data-Selected-socioeconomic-indicators-in-C/kn9c-c2s2 |
| CMAP snapshots | https://cmap.illinois.gov/data/community-data-snapshots/ |

This source contains socioeconomic indicators by community area, including
crowded housing percentage, poverty, unemployment, education, age dependency,
and per-capita income.

Treat this as an SCD Type 2 opportunity. If multiple census or snapshot years
are collected, version `dim_location` by effective date range.

### 4. Chicago Hourly Weather

Hourly weather enrichment for date-hour joins.

| Field | Value |
|---|---|
| Source | Open-Meteo Historical Weather API |
| Format | JSON |
| Size | ~365,000 hourly rows for 2018-2024 |
| API | `https://archive-api.open-meteo.com/v1/archive?latitude=41.85&longitude=-87.65&start_date=2018-01-01&end_date=2024-12-31&hourly=temperature_2m,precipitation,wind_speed_10m,weather_code,relative_humidity_2m&timezone=America%2FChicago` |

Weather variables to keep:

| Variable | Warehouse use |
|---|---|
| `temperature_2m` | Temperature in Celsius |
| `precipitation` | Rain or snow amount in mm |
| `wind_speed_10m` | Wind speed in km/h |
| `weather_code` | WMO weather code, optionally mapped to clear/rain/snow/storm categories |
| `relative_humidity_2m` | Humidity percentage |

Join weather to crimes by local date and hour.

### 5. Chicago Police Arrests

Optional enrichment source.

| Field | Value |
|---|---|
| Source | City of Chicago Data Portal |
| Format | CSV |
| Size | ~700,000 rows |
| Portal | https://data.cityofchicago.org/Public-Safety/Arrests/dpt3-jri9 |

Use this only if the project needs deeper arrest analysis. It can enrich crime
analytics with arrest demographics such as age, sex, and race. Keep the join
logic explicit, because arrest records may not match one-to-one with crime
incidents.

## Source Summary

| # | Dataset | Format | Approx rows | Role |
|---|---|---:|---:|---|
| 1 | Chicago Crimes 2018-2024 | CSV | 1.5M | Main fact source |
| 2 | IUCR Crime Codes | CSV | 400 | Crime type dimension |
| 3 | Community Area Socioeconomics | CSV | 77 per snapshot | Location SCD2 enrichment |
| 4 | Chicago Hourly Weather | JSON | 365k | Weather dimension/enrichment |
| 5 | Chicago Arrests | CSV | 700k | Optional arrest enrichment |

The combined source volume is comfortably above 100,000 rows and includes both
CSV and JSON, which supports the data-lake and data-variety requirements.

## Current Ingestion Flow

The active implemented flow ingests the Chicago Crime Reports source into the
raw S3 data lake.

Infrastructure:

- Terraform manages AWS infrastructure in `terraform/`.
- The raw S3 bucket is
  `data-warehouse-final-238027390687-ap-southeast-1-raw`.
- Raw Chicago crime files are stored under `raw/chicaho_crime/`.
- EventBridge Scheduler invokes the Lambda daily at 2 AM
  `America/Chicago`.
- The Lambda function is `data-warehouse-final-fetch-chicago-crime`.

Storage behavior:

- Raw storage is append-only. Do not update existing raw CSV files in place.
- Raw files are partitioned by ingestion date:
  `raw/chicaho_crime/ingest_date=YYYY-MM-DD/`.
- Historical backfill files are monthly range files named like
  `chicago_crime_2019-01-01_to_2019-01-31_<timestamp>.csv`.
- Future scheduled files are daily files named like
  `chicago_crime_2026-05-01_<timestamp>.csv`.
- Duplicate source dates can exist in raw if a date is re-fetched. Downstream
  staging or curated tables must deduplicate by the Chicago source `ID`.

Backfill status:

- One-time historical backfill has been run from `2019-01-01` through
  `2026-04-30`.
- The backfill stopped at `2026-04-30` because the source excludes the most
  recent seven days and the project date at the time was `2026-05-08`.
- The cron will continue loading one source day per run using an 8-day lookback.

Daily scheduler behavior:

- On each scheduled run, the Lambda fetches `current Chicago date - 8 days`.
- Example: a run on `2026-05-09` fetches source date `2026-05-01`.
- The 8-day lookback is a conservative buffer for the source's stated
  seven-day exclusion window.

## Implementation Guidance

- Preserve raw downloads before transformation.
- Keep raw, staged, and curated data clearly separated.
- Prefer reproducible ingestion scripts over manual downloads when practical.
- Normalize source column names during staging.
- Validate row counts after each ingestion and transformation step.
- Keep source URLs, extraction timestamps, and date filters in metadata.
- Use explicit timezone handling for crime and weather timestamps.
- Treat nullable location, latitude, longitude, and community area fields
  defensively.
- Avoid committing generated data extracts, credentials, local profile files, or
  large build artifacts unless the repository explicitly requires them.

## AWS Guidance

- Always read the local config before AWS CLI, SDK, Terraform, CDK, or deployment
  work.
- Use the configured profile with commands, for example
  `aws --profile <profile-name> ...`.
- Use Terraform for AWS infrastructure changes unless a task explicitly asks for
  a different provisioning approach.
- If code needs AWS profile configuration, prefer environment variables or local
  config over hardcoding the profile in source files.
- If the configured profile is missing from the machine, report that clearly and
  ask the user to configure it locally.
