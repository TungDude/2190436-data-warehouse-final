# AWS Architecture: Chicago Crime Data Warehouse

This document is the **AWS service blueprint** for the project. It complements
`docs/dimensional-design.md` (which is the *schema* design) by specifying
**what runs where**, **why each service was chosen**, and **how the pipeline
maps onto the concepts taught in class**.

It is graded against:

- `requirements/Project_DW_Big_Data_Implementation_2025.md` — rubric (20 %).
- The DW course (2190436) — `docs/lectures/01..06`.
- The Big Data course (2190518) — `docs/lectures/07..14`.

Every architectural choice below is annotated with the lecture(s) it follows,
so the marker can audit the design against the course material directly.

---

## 1. Goals (and Anti-Goals)

### Goals

1. Hit every line item in the project rubric (Slide 5–6 of the requirements):
   data sources, DW + ETL, big data component, automatic workflow, BI.
2. Stay faithful to the **course curriculum** — use the architectures, layers,
   and tools taught in Lectures 01, 07, 11, and 13.
3. Keep **moving parts minimal**. The data is ~2.5 M rows total; we do not
   need a hyperscale stack, we need a clean, defensible one.

### Anti-goals (what we are explicitly *not* building)

| Tempting thing | Why we skip it |
|---|---|
| Amazon Redshift | RDS PostgreSQL is sufficient at our row counts. Redshift adds cost and ops without changing the answer to any rubric question. |
| Apache Kafka / MSK / Kinesis | Lecture 14 material, but no streaming requirement — all sources are batch APIs. |
| EMR clusters | Glue (managed Spark) is the same engine without cluster management. |
| Lake Formation, fine-grained access control | Single project AWS account; one team. Overkill. |
| AWS DMS | No OLTP database to replicate; sources are public REST/CSV APIs. |
| ElastiCache / DynamoDB | The KV-store option in the rubric (Slide 6) is a **choice**, not a mandate — see §6 for the picked Big Data justification. |
| ECS / Fargate | Lambda + Glue cover compute; containers add ops with no benefit here. |

---

## 2. Course-Concept Mapping

The architecture is intentionally a one-to-one mapping of two slide-deck
diagrams onto AWS:

### 2.1 The Kimball DW component model (Lecture 01, Slide 14)

```
Operational Source Systems  →  Staging Area  →  Presentation Area  →  Data Access
```

| Lecture layer | This project's AWS realisation |
|---|---|
| Operational Source | 5 public APIs (Chicago portal, Open-Meteo). See `CLAUDE.md`. |
| Staging Area (ETL) | **S3 raw zone** (immutable landing) + **Glue PySpark jobs**. |
| Presentation Area | **Amazon RDS for PostgreSQL** holding the star schema (`dw.*`). |
| Data Access (BI) | **Amazon QuickSight** with SPICE backed by RDS. |

### 2.2 The Medallion / Lakehouse model (Lecture 13, Slides 47–79)

The class explicitly teaches the bronze / silver / gold zoning:

> *"Lakehouse design pattern organising data into bronze (raw), silver
> (cleaned), and gold (aggregated) layers for progressive data quality
> refinement."* — Lecture 13 Slide 47.

We adopt those exact names so the architecture is recognisable to the marker:

| Layer | Location | Format | Role |
|---|---|---|---|
| **Bronze** | `s3://…-raw/raw/<source>/ingest_date=…/` | CSV + JSON (as published) | Immutable source-of-truth landing zone. **Append-only.** |
| **Silver** | `s3://…-raw/standardized/<source>/` *(planned)* | **Parquet** (Lecture 09 — columnar) | Type-cast, deduped, normalised column names. Crawled by Glue Catalog and queryable from Athena. |
| **Gold** | RDS PostgreSQL `dw.*` schema | Relational star schema | The dimensional model in `docs/dimensional-design.md`, ready for QuickSight. |

This gives us the **DW + Data Lake coexistence** pattern the rubric asks for
(Slide 1: *"Coexist between Traditional DE & Modern DE (Big Data)"*) and
matches Lecture 01 Slide 25 ("DW and DL used together") and Lecture 07
Slides 6–7 (DW vs DL contrast table).

---

## 3. End-to-End Architecture

```
                                  +-----------------------------------+
                                  |  EventBridge Scheduler (cron)    |
                                  |  daily 02:00 America/Chicago     |
                                  +-----------------+-----------------+
                                                    |
            +---------------------+-----------------+-----------------+---------------------+
            |                     |                 |                 |                     |
            v                     v                 v                 v                     v
  +-------------------+ +-------------------+ +-------------+ +----------------+ +--------------------+
  | Lambda           | | Lambda           | | Lambda      | | Lambda         | | Lambda             |
  | fetch-chicago-   | | fetch-iucr-      | | fetch-      | | fetch-weather- | | fetch-arrests      |
  | crime  *active*  | | codes (one-shot) | | socio-econ  | | open-meteo     | |  (optional)        |
  +---------+---------+ +---------+---------+ +------+------+ +-------+--------+ +----------+---------+
            |                     |                 |                 |                     |
            +---------------------+-----------------+-----------------+---------------------+
                                                    |
                                                    v
                              +-----------------------------------------+
                              |  S3 Bronze (raw)                        |
                              |  s3://...-raw/raw/<source>/             |
                              |    ingest_date=YYYY-MM-DD/              |
                              |  CSV + JSON, immutable, versioned       |
                              +-----------------+-----------------------+
                                                |
                                                v
                              +-----------------------------------------+
                              |  AWS Glue Crawler                       |
                              |  → AWS Glue Data Catalog                |
                              |  (databases: bronze, silver)            |
                              +-----------------+-----------------------+
                                                |
                                                v
                              +-----------------------------------------+
                              |  AWS Glue ETL Job (PySpark)             |
                              |  bronze → silver                         |
                              |   • type cast, null handling             |
                              |   • dedup latest by source PK            |
                              |   • write Parquet, partitioned by year   |
                              +-----------------+-----------------------+
                                                |
                                                v
                              +-----------------------------------------+
                              |  S3 Silver (standardized)               |
                              |  s3://...-raw/standardized/<source>/    |
                              |  Parquet, year=YYYY/                    |
                              |  ← also queryable via Athena ad hoc     |
                              +-----------------+-----------------------+
                                                |
                                                v
                              +-----------------------------------------+
                              |  AWS Glue ETL Job (PySpark)             |
                              |  silver → gold (RDS)                     |
                              |   • surrogate-key assignment             |
                              |   • SCD1 / SCD2 merge                    |
                              |   • null → "Unknown" coalesce            |
                              |   • upsert by natural key                |
                              +-----------------+-----------------------+
                                                |
                                                v
                              +-----------------------------------------+
                              |  Amazon RDS for PostgreSQL 16  (Gold)   |
                              |   schema dw.* (star schema)             |
                              |    fact_crime / fact_arrest             |
                              |    dim_date / dim_time_of_day /         |
                              |    dim_location / dim_crime_type /      |
                              |    dim_weather / dim_crime_flags /      |
                              |    dim_arrestee + bridge_arrest_charge  |
                              +-----------------+-----------------------+
                                                |
                                                v
                              +-----------------------------------------+
                              |  Amazon QuickSight                      |
                              |   • SPICE dataset on RDS                |
                              |   • Dashboard 1: Overview               |
                              |   • Dashboard 2: Detail                 |
                              +-----------------------------------------+

  Orchestration: AWS Glue Workflows (crawler → bronze→silver → silver→gold)
                 triggered by EventBridge on completion of all five fetch Lambdas.
```

---

## 4. AWS Services — Roles and Rationale

| Service | Role | Lecture link | Why this and not something else |
|---|---|---|---|
| **Amazon S3** | Bronze + Silver storage; the data lake. | Lec 07 (data lake), Lec 09 (Parquet) | Cheap, durable, native to every AWS analytics tool. Required by rubric. |
| **AWS Lambda** | Lightweight ingest workers — one per source. | — | Sources are < 50 MB/day after 8-day-lookback; Lambda fits cleanly within the 15-minute / 10 GB ephemeral limit. Already implemented for Chicago Crime. |
| **Amazon EventBridge Scheduler** | Cron trigger for ingest Lambdas. | Lec 13 (scheduling concept) | Native cron without standing infra; already used by `data-warehouse-final-fetch-chicago-crime`. |
| **AWS Glue Crawler** | Auto-discover schemas of bronze/silver datasets. | Lec 07 Slide referencing "AWS Glue Data Catalog" | Saves writing/maintaining DDL for the lake; needed for Athena queries on silver. |
| **AWS Glue Data Catalog** | Single Hive-compatible metastore for the lake. | Lec 07, Lec 09 (Hive metastore concept) | The lakehouse pattern's metadata layer (Lecture 07 Slide 188 table). |
| **AWS Glue ETL (PySpark)** | bronze→silver and silver→gold transforms. | **Lec 11 (Spark)**, Lec 07 Slide 229 | This is where our "Big Data component" lives — see §6. Managed Spark with no cluster ops. |
| **Amazon RDS for PostgreSQL 16** | Gold layer — the dimensional warehouse. | Lec 01 (presentation area), Lec 04 (SCDs run easiest on a RDBMS) | Star schema with referential integrity, identity surrogates, `INSERT … ON CONFLICT` for SCD merges. Decided in `dimensional-design.md` §8.1. |
| **Amazon QuickSight** | BI dashboards. | Lec 01 (data access tier) | Required by rubric (Slide 5–6); native RDS connector; SPICE for fast dashboards. |
| **Amazon Athena** *(supporting)* | Ad-hoc SQL on silver Parquet for data exploration / debugging. | Lec 07 Slide 188 (Trino / Athena column) | Free per-query model; lets us validate silver data without spinning up RDS access from the dev box. |
| **AWS Glue Workflows** | Orchestrate crawler → bronze→silver job → silver→gold job. | Lec 13 (workflow orchestration concept) | See §7 — picked over MWAA for cost/complexity reasons; Airflow remains the lecture's reference implementation. |
| **AWS IAM, KMS, VPC** | Plumbing — least-priv roles, S3/RDS encryption, RDS subnet group. | — | Standard cloud hygiene; already partially in `terraform/main.tf`. |

---

## 5. Data Sources — Ingestion Pattern

All five sources land in S3 bronze under `raw/<source>/ingest_date=…/`. Each
source gets its own Lambda (one already implemented, four to add). The
**ingestion contract** is identical so the Glue jobs can treat them
uniformly:

| # | Source | Format | Frequency | Lambda | Status |
|---|---|---|---|---|---|
| 1 | Chicago Crimes 2018-now | CSV via Socrata | Daily (T-8) | `fetch-chicago-crime` | **Implemented** (see `CLAUDE.md` "Current Ingestion Flow") |
| 2 | IUCR Crime Codes | CSV | One-shot + monthly refresh | `fetch-iucr-codes` | Planned |
| 3 | Community Area Socioeconomics | CSV | Annual snapshot (multiple years for SCD2) | `fetch-socioeconomics` | Planned |
| 4 | Open-Meteo Hourly Weather | JSON | One-shot historical + daily catch-up | `fetch-weather` | Planned |
| 5 | Chicago Police Arrests | CSV | Daily (T-8) | `fetch-arrests` *(optional)* | Planned (only if `fact_arrest` is in scope) |

Each Lambda is a thin wrapper:
*HTTP GET → write to `raw/<source>/ingest_date=YYYY-MM-DD/<file>_<ts>.<ext>`.*
No transformation in the Lambda — that is the silver job's responsibility,
which keeps the bronze immutable per the medallion contract (Lec 13 Slide 59).

---

## 6. Big Data Component — Picked Justification

Rubric Slide 6 (4 %): *"Include one Big Data technology with justification,
e.g., Spark → Volume, Data Lake → Variety, KV DB → fast lookup."*

We pick **Apache Spark on AWS Glue** as the primary Big Data component, and
**S3 as the data lake** as a complementary one. Both are visible in the
diagram and both are taught in class.

| Option | Picked? | Justification |
|---|---|---|
| **Spark (Glue PySpark)** | **Yes — primary** | Volume: 1.5 M crimes + 0.7 M arrests + 0.36 M weather rows ≈ **2.5 M rows** total, with multi-source joins (crime × weather by hour, crime × IUCR by code, crime × socioeconomics by community area × snapshot year). Spark's in-memory DAG engine and DataFrame joins (Lecture 11 Slides 41–86) are the right tool. Single-host pandas would still work but would not match the course's *data-engineering* expectation. |
| **Data Lake (S3 + Parquet + Glue Catalog)** | **Yes — supporting** | Variety: we ingest CSV (4 sources) and JSON (1 source) into one bucket, schema-on-read, then materialise Parquet (Lec 09 columnar) for Spark to chew. This *is* the Lecture 07 Slide 188 lakehouse stack: S3 + Glue Catalog + Spark + Athena. |
| KV store (Redis / DynamoDB) | No | We have no fast-lookup workload. The rubric example "infrequent updates + fast lookup" does not match this dataset — adding ElastiCache would be cargo-culting Lecture 10 to score points. |
| Hive (EMR) | No | Hive on EMR is a heavier-weight implementation of what Glue Catalog + Athena already give us (Lecture 09 vs. Lecture 07 Slide 188). |
| Spark ML | No | The rubric's prescriptive/predictive analytics ladder (Slide 2) is **referenced**, not required. Adding a model just for points is over-engineering. |

The big-data argument we will make on the rubric form: **"Spark for Volume,
S3 + Parquet for Variety, with Glue managing both."**

---

## 7. Automatic Workflow (Rubric §4 — 1 %)

The rubric accepts **Glue Scheduler and/or Airflow**. We pick:

> **EventBridge Scheduler → ingest Lambdas → Glue Workflow (crawler + 2
> Spark jobs).**

| Option | Picked? | Trade-off |
|---|---|---|
| EventBridge + **Glue Workflows** | **Yes** | Native, no standing infra, free, fits inside the existing Terraform stack. |
| **Airflow on EC2** (Lecture 13's lab) | No (kept as alternative) | Demonstrates the lecture directly, but adds an EC2 instance + Airflow ops we do not need at this scale. We *do* show an equivalent DAG diagram in the Video 1 presentation to acknowledge the lecture. |
| Amazon **MWAA** | No | $0.49/hr base ≈ $350/month — disproportionate to a 20 % course project (Lecture 13 Slide 323 explicitly flags MWAA as "not free"). |

The Glue Workflow is structured exactly like a small Airflow DAG:

```
   trigger: all five Lambdas finished today's ingest
       │
       ▼
   crawler:  refresh bronze partitions in Glue Catalog
       │
       ▼
   job:      bronze → silver  (PySpark, parallel per source)
       │
       ▼
   crawler:  refresh silver tables
       │
       ▼
   job:      silver → gold    (PySpark, applies SCD merges into RDS)
       │
       ▼
   sensor:   row-count + referential-integrity asserts
```

This is the medallion DAG from Lecture 13 Slide 79, just rendered with Glue
primitives.

---

## 8. BI Layer (Rubric §5 — 4 %)

Two QuickSight dashboards, both backed by **SPICE imported from RDS**:

| Dashboard | Audience | Suggested visuals |
|---|---|---|
| **Overview** | Executive — answers Q1, Q3 from `dimensional-design.md` §3.0 | KPIs (total reports, arrest rate); time series of monthly crime count; choropleth of community areas; donut of primary type distribution. |
| **Detail** | Analyst — answers Q2, Q4, Q5 | Heatmap (hour of day × day of week); scatter of weather (precip / temp band) vs. crime category; SCD2-aware filter "show indicators *as of* the event date"; arrest trend by district. |

QuickSight's RDS connector + SPICE keeps load off the warehouse and gives
sub-second dashboard interactions. SPICE refresh is scheduled to run an
hour after the gold-layer Glue job finishes.

---

## 9. Security & Cost Posture

This is a course project on a shared AWS account. The architecture sticks
to defaults that are safe and cheap:

- **S3**: `BlockPublicAccess` on, SSE-S3 (AES256), versioning on (already in
  `terraform/main.tf`).
- **RDS**: deployed in private subnets, no public IP; QuickSight reaches it
  via VPC connection. Storage encrypted with default AWS-managed KMS key.
- **Lambdas**: scoped IAM roles — one role per Lambda, only the S3 prefix
  it writes to.
- **Glue jobs**: dedicated role with read on S3 raw, read/write on
  S3 silver, JDBC on the RDS DW user (least-priv against `dw.*`).
- **Cost expectations** (rough order, ap-southeast-1, us-east-1
  comparable):

| Item | Indicative monthly cost |
|---|---|
| S3 storage (~5 GB) + requests | < $1 |
| Glue Workflows (≈ 4 DPU-hours / day) | ~$15 |
| RDS db.t4g.micro (single-AZ) | ~$15 |
| QuickSight Author seat + 1 reader | $24 + per-session |
| Lambdas + EventBridge | < $1 |

Total well under $60/month — appropriate for a 20 % project.

---

## 10. Mapping to the Project Rubric

| # | Rubric line item | Weight | Where in this architecture |
|---|---|---:|---|
| 1 | Data sources (≥ 1, prefer multiple) | 2 % | §5 — five distinct sources, CSV + JSON, joined across the model. |
| 2 | DW + ETL — 4-step model, ≥ 1 fact, conformed bus matrix, **all dims SCD**, no aggregate fact | 4 % | `dimensional-design.md` §3–§6 (design); §3 + §4 of this doc (Glue PySpark ETL into RDS). |
| 3 | Big Data component with justification | 4 % | §6 — Spark on Glue (Volume) + S3/Parquet data lake (Variety). |
| 4 | Automatic workflow | 1 % | §7 — EventBridge → Glue Workflow DAG. |
| 5 | BI ≥ 2 dashboards on QuickSight | 4 % | §8 — Overview + Detail. |
| 6 | Two presentation videos | 5 % | Out of scope for this doc; covered by §1 of `dimensional-design.md` and the diagrams here (re-used in Video 1). |

---

## 11. Current Status (as of 2026-05-10)

What is **already built** (per `CLAUDE.md` "Current Ingestion Flow"):

- Terraform-managed S3 bronze bucket: `data-warehouse-final-238027390687-ap-southeast-1-raw`.
- Lambda `data-warehouse-final-fetch-chicago-crime` + EventBridge daily 02:00
  America/Chicago, with 8-day lookback.
- Historical backfill 2019-01-01 → 2026-04-30 in
  `raw/chicaho_crime/ingest_date=…/`.

What is **next** (in order of dependency):

1. Provision RDS PostgreSQL 16 (Terraform). Apply `dimensional-design.md`
   DDL into schemas `raw_stg`, `dw_staging`, `dw`.
2. Add the four remaining ingest Lambdas (§5 sources 2–5).
3. Add Glue Crawler + Glue Database for bronze and silver.
4. Write the bronze → silver Glue PySpark job (one job, source-parameterised).
5. Write the silver → gold Glue PySpark job (SCD-aware merge into RDS).
6. Wire the Glue Workflow (§7) and a single EventBridge rule that fires it.
7. Build the two QuickSight dashboards (§8).

Each step is independently mergeable; nothing in here forces a big-bang
release.

---

## 12. Open Questions

These should be answered before the silver→gold job is written; they shape
the SQL but not the AWS topology.

1. **Is `fact_arrest` in scope?** (Open question §10.2 of
   `dimensional-design.md`.) If yes, source 5 ingest Lambda is required.
2. **How many socioeconomic snapshots will we ingest** (1, 3, all
   available)? Drives the volume of `dim_location` SCD2 versions.
3. **Glue 4.0 vs Glue 5.0** for the PySpark jobs? Default to **Glue 5.0**
   (Spark 3.5) unless a connector forces otherwise.
4. **VPC layout for RDS + Glue** — reuse the default VPC or provision a
   project VPC? Default is fine for a course project; a dedicated one makes
   IAM + networking cleaner if we have time.
