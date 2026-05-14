# Silver → Gold Implementation Plan

This document plans the next slice of the pipeline: moving from the
silver Parquet zone on S3 into the gold dimensional warehouse in
Amazon RDS for PostgreSQL.

It is a **plan only** — no code or Terraform here. The schema is
already designed in `docs/dimensional-design.md` and the AWS topology
in `docs/architecture.md`; this document just describes the order,
shape, and trade-offs of the work that turns those docs into running
infrastructure.

References used throughout:

- `docs/architecture.md` §2.2 (medallion), §3 (end-to-end diagram),
  §4 (services), §7 (workflow), §11 (current status & next steps).
- `docs/dimensional-design.md` §3 (4-step process), §4 (bus matrix),
  §5 (SCD strategy), §8 (RDS DDL sketches), §9 (ETL flow).

---

## 1. Scope

**In scope — purely S3 silver → RDS gold.** Provision RDS
PostgreSQL 16, materialise the `raw_stg` / `dw_staging` / `dw` schemas
from `dimensional-design.md` §8.2, and write the Glue PySpark job(s)
that read silver Parquet from S3 and apply SCD-aware merges into
`dw.*`. The deliverable is a populated, queryable warehouse in RDS;
**BI / dashboards are not part of this slice and are not referenced
again in this document.**

**Out of scope** (deferred to later slices, listed in
`architecture.md` §11 next-steps):

- The four other bronze→silver ingests (IUCR, socioeconomics, weather,
  arrests) — silver→gold *design* covers them, but only the
  `chicago_crime`-driven parts can be loaded end-to-end today.
- VPC redesign (default VPC is fine for V1 per `architecture.md` §12 Q4).
- Aurora upgrade (`dimensional-design.md` §10.2 Q5).

---

## 2. Hard Dependency on Other Sources

Silver currently contains only `standardized/chicago_crime/`. Several
gold tables cannot be **fully** populated until their feeder sources
land in silver. The plan therefore has to choose between:

| Strategy | What it means | Trade-off |
|---|---|---|
| **A — End-to-end now, partial population** | Build all of `dw.*`, including `dim_weather`, `dim_crime_type` SCD2, `dim_location` SCD2 socioeconomics. Where the feeder source is missing, fact rows resolve to the reserved "Unknown" surrogates (`dimensional-design.md` §8.5). Backfill real values when sources 2-5 ship. | The schema is faithful to the design from day one. SQL queries against `dw.*` work but most rows point at "Unknown" until the rest of silver lands. |
| **B — Chicago-crime-only subset now** | Defer `dim_weather`, the SCD2 columns of `dim_location`, and `dim_crime_type` enrichment. Build only `fact_crime` + `dim_date` + `dim_time_of_day` + a thin `dim_location` (geographic NK only) + a thin `dim_crime_type` (IUCR + primary_type carried from the crime feed itself) + `dim_crime_flags`. | Less placeholder noise, but a second migration is needed when sources 2-4 arrive — and it will touch live `dw.*` tables. |

**Recommended: Strategy A.** Reasons:

1. The reserved "Unknown" surrogate row pattern is already required by
   the design (`dimensional-design.md` §8.5) — using it is not a hack,
   it is the documented null-FK contract.
2. Adding new dim columns later means an SCD2 retrofit on existing
   rows, which is much more error-prone than starting with the columns
   in place and back-filling values.
3. The bus matrix in `dimensional-design.md` §4 stays intact and the
   acceptance checklist in §10.3 can be evaluated against the actual
   shape we will ship.

The rest of this plan assumes Strategy A.

---

## 3. Work Breakdown

The work splits cleanly into five tracks. Tracks 1 and 2 are
prerequisites for 3-5 and can run in parallel.

### Track 1 — RDS provisioning (Terraform)

Files affected: `terraform/rds.tf` (new), `terraform/variables.tf`,
`terraform/outputs.tf`, possibly `terraform/network.tf` (new if we
introduce a dedicated subnet group).

Resources to add:

- `aws_db_subnet_group` covering at least two private subnets in
  ap-southeast-1 (default VPC is acceptable for V1).
- `aws_security_group` for the RDS instance: ingress on 5432 from the
  Glue connection security group only.
- `aws_security_group` for the Glue JDBC connection.
- `aws_db_parameter_group` (PostgreSQL 16 family) — at minimum enable
  `pgaudit` is **out of scope**; defaults are fine.
- `aws_db_instance` — engine `postgres`, engine_version `16.x`,
  instance_class `db.t4g.micro` (per `architecture.md` §9 cost
  table), `storage_encrypted = true` with the default AWS-managed
  KMS key, `publicly_accessible = false`, `multi_az = false`,
  `deletion_protection = true`, automated backup retention 7 days.
- Master credentials stored in **AWS Secrets Manager**
  (`aws_secretsmanager_secret` + `aws_secretsmanager_secret_version`),
  *not* in tfvars. The Glue job reads the secret at runtime.
- `aws_glue_connection` of type `JDBC` referencing the RDS endpoint and
  the Glue connection security group. Required so the Glue job can
  reach RDS in a VPC.

Outputs to add: `rds_endpoint`, `rds_secret_arn`, `rds_database_name`,
`glue_jdbc_connection_name`.

Open question: a dedicated DB subnet group lets us tighten the
security-group rules; reuse of default subnets is faster but mixes
the DB with whatever else is in those subnets. Default subnets are
acceptable for V1 (per `architecture.md` §12 Q4).

### Track 2 — DDL bootstrap

Files affected: `sql/dw_schema.sql` (new), `sql/dw_seed.sql` (new),
optionally a Terraform `null_resource` + `local-exec` that applies
them on first apply.

The DDL is already sketched in `dimensional-design.md` §8.3 — this
track converts the sketch into a runnable script.

Per `dimensional-design.md` §8.2, three schemas:

| Schema | Used by | Lifecycle |
|---|---|---|
| `raw_stg` | Silver→gold extract step; one table per silver dataset, types preserved | Truncated and re-loaded each run |
| `dw_staging` | Silver→gold transform step; cleansed, joined, deduped | Truncated and re-loaded each run |
| `dw` | Star schema, queried by downstream SQL consumers | Long-lived, idempotent merges |

Tables to create (all in `dw.*`, per `dimensional-design.md` §8.3):

- `dim_date` — smart key `YYYYMMDD`, SCD0, prepopulated for
  2018-01-01..2030-12-31 (8 years × 365.25 ≈ 2,922 rows).
- `dim_time_of_day` — smart key 0..23, SCD0, prepopulated with 24 rows.
- `dim_location` — SCD2 with embedded SCD1 attributes (Type 7).
- `dim_crime_type` — SCD2.
- `dim_weather` — SCD0 hourly observation.
- `dim_crime_flags` — junk dim, SCD1, prepopulated with 5 rows
  (0 = unknown plus the 4 boolean combinations, per
  `dimensional-design.md` §8.4).
- `dim_arrestee` — SCD1. Created in V1 even if `fact_arrest` is not
  populated, so the schema stays stable.
- `fact_crime` — transaction-grain, atomic.
- `fact_arrest` — created but not necessarily loaded (deferred behind
  source 5; `dimensional-design.md` §10.2 Q1).
- `bridge_arrest_charge` — same status as `fact_arrest`.

Seed data to load on bootstrap:

- All "Unknown" / "Not applicable" rows from
  `dimensional-design.md` §8.5 (`0` rows in every dim plus `-1` in
  `dim_weather`).
- The full `dim_date` and `dim_time_of_day` populations.
- The 5-row `dim_crime_flags` junk dim.

Open question: deploy DDL via Terraform `local-exec`, or a one-shot
Lambda invoked by Terraform, or manually with `psql`? The Terraform
`local-exec` couples DDL to plan/apply runs and surfaces failures
in the apply log, but needs network access to RDS from wherever
Terraform runs. **Recommendation:** a small bootstrap Lambda
(reusing the Lambda execution role pattern) that runs the DDL once,
triggered by Terraform via `aws_lambda_invocation`. This keeps the
operator's laptop out of the RDS VPC.

### Track 3 — Glue silver → gold job

Files affected: `src/glue_jobs/silver_to_gold/main.py` (new),
`src/glue_jobs/silver_to_gold/registry.py` (new),
`src/glue_jobs/silver_to_gold/common.py` (new),
`src/glue_jobs/silver_to_gold/dimensions/*.py` (new, one per dim),
`src/glue_jobs/silver_to_gold/facts/chicago_crime.py` (new),
`terraform/glue.tf` (extend — see Track 4).

The job layout mirrors the existing bronze→silver convention so the
two are intelligible side-by-side:

- `main.py` is the Glue entry point — accepts `--target` so the
  workflow can route dim loads and fact loads to the same job binary.
- `dimensions/<name>.py` implements `load(spark, jdbc_props,
  silver_catalog)` for one dim, handling its specific SCD type.
- `facts/chicago_crime.py` implements the `fact_crime` load.

Per-dimension responsibilities (mapping
`dimensional-design.md` §5):

| Dim | SCD type | Reader source (today) | Reader source (when other sources land) |
|---|---|---|---|
| `dim_date` | Type 0 | DDL seed | unchanged |
| `dim_time_of_day` | Type 0 | DDL seed | unchanged |
| `dim_crime_flags` | Type 1 | DDL seed | unchanged |
| `dim_location` | Type 2 (hybrid) | Distinct `(community_area, district, ward, beat)` from silver `chicago_crime` | Adds socioeconomic columns from silver `socioeconomics` (source 3) |
| `dim_crime_type` | Type 2 | Distinct `(iucr, primary_type, description, fbi_code)` from silver `chicago_crime` | Replaced/enriched by silver `iucr_codes` (source 2) including `index_code` and `active` |
| `dim_weather` | Type 0 | Empty (only the `-1` reserved row) | Hourly observations from silver `weather` (source 4) |
| `dim_arrestee` | Type 1 | Empty | Distinct demographics from silver `arrests` (source 5) |

Per-dim load contract:

1. Read silver source via Glue Catalog (`bronze`-style: `spark.sql("…
   FROM silver_db.<table>")`).
2. Compute the SCD2-tracked column hash (`scd_hash`) for SCD2 dims.
3. Left-join against current `dw.<dim>` on natural key.
4. Three row classes: **new** (no current row), **changed** (hash
   differs from current row), **unchanged**.
5. SCD2: expire changed rows (`UPDATE … SET is_current = FALSE,
   scd_end_date = today`), insert new + new-version rows.
6. SCD1: `INSERT … ON CONFLICT (natural_key) DO UPDATE`.
7. SCD0: insert-only, skip existing.

`fact_crime` load contract:

1. Read silver `chicago_crime` partitions, **excluding** the sentinel
   `_ingest_year = 9999` (per `CLAUDE.md` Silver-Layer section).
2. Coalesce null FKs to the reserved `0` / `-1` rows from
   `dimensional-design.md` §8.5 — do **not** drop fact rows on null.
3. Resolve FKs:
   - `dim_date` by `YYYYMMDD` derived from `date` (occurrence) and
     `updated_on` (report) — two separate joins, role-playing
     (`dimensional-design.md` §6.3).
   - `dim_time_of_day` by hour-of-day of `date`.
   - `dim_location` by `(community_area, district, ward, beat)` **as
     of the occurrence date** — i.e., the SCD2 row whose
     `[scd_start_date, scd_end_date)` contains the event.
   - `dim_crime_type` by `iucr` as of the occurrence date (also SCD2).
   - `dim_weather` by `(date_key, hour)` of the occurrence — falls to
     `-1` until weather source lands.
   - `dim_crime_flags` by `(is_arrest, is_domestic)`.
4. Compute derived measures: `incident_count = 1`,
   `is_arrest`/`is_domestic` as `SMALLINT`, `hours_to_update`
   from `updated_on - date`.
5. **Upsert by `crime_id`** (the natural key, per
   `dimensional-design.md` §3.2.1). This makes the fact load idempotent
   — re-running a day's load does not duplicate rows.
6. Write through the Glue JDBC connection from Track 1.

Idempotency posture: every step is either a truncate-and-reload
(staging) or an upsert by natural key (dims, fact). Re-running the
workflow for a date the workflow has already processed must produce
zero net change in `dw.*`. This satisfies
`dimensional-design.md` §10.3 last checkbox.

### Track 4 — Workflow extension

Files affected: `terraform/glue.tf`.

The existing workflow today is `bronze crawler → per-source job →
silver crawler`. Silver→gold extends this DAG to:

```
bronze crawler
    │
    ▼
per-source bronze→silver job  (fan out, one per source)
    │
    ▼
silver crawler
    │
    ▼
silver→gold dims job  (loads all dims; runs once per workflow run)
    │
    ▼
silver→gold facts job  (loads fact_crime; depends on all dims being
                        loaded so FK resolution finds the right SCD2
                        version)
    │
    ▼
(optional) row-count + referential-integrity sensor
```

This matches the DAG sketch in `architecture.md` §7. Implementation:

- One new `aws_glue_job` for dims (`...-silver-to-gold-dims`) and one
  for facts (`...-silver-to-gold-facts`). Two jobs rather than one
  because the AND-predicate semantics from PR #1's review apply here
  too — distinct `job_name`s make the dependency unambiguous.
- A new `aws_glue_trigger` of type `CONDITIONAL` with predicate
  "silver crawler SUCCEEDED" → starts the dims job.
- A second `aws_glue_trigger` of type `CONDITIONAL` with predicate
  "dims job SUCCEEDED" → starts the facts job.
- Optionally a third trigger / Lambda that runs a row-count
  reconciliation query and fails the workflow on mismatch.

The existing daily 03:30 America/Chicago EventBridge schedule is
unchanged — it starts the workflow, the workflow runs the full chain.

Both new jobs reference the Glue JDBC connection from Track 1 in
their `connections` block.

IAM additions:

- The silver→gold Glue role needs `secretsmanager:GetSecretValue` on
  the RDS master secret.
- Same role needs the existing S3-read scope (already granted for
  bronze→silver).
- Same role needs the `AWSGlueServiceRole` managed policy (already
  attached for the existing job).

### Track 5 — Tests

Files affected: `tests/glue_jobs/silver_to_gold/*` (new),
`tests/fixtures/silver/chicago_crime/*` (new — small Parquet
fixtures with known shape).

Local unit tests use the same JDK 17 + pyspark 3.5 harness as the
bronze→silver tests. The RDS portion cannot be tested locally without
a Postgres instance; options:

1. Use `pytest-postgresql` (spins up a local Postgres for the test).
2. Use a JDBC mock (e.g. a `DataFrameWriter` recorder) and verify the
   write *plan*, not the actual writes.
3. Skip JDBC writes locally; rely on the smoke-test pattern from
   `terraform/README.md` to validate end-to-end in AWS.

**Recommendation:** option 1 for the dim-load logic (SCD2 merge is
gnarly enough that we want a real Postgres to assert against), option
3 for the fact-load logic (the SCD-aware FK lookups are easier to
exercise with a real silver fixture than a synthetic one). Option 2
adds a third pattern without adding much coverage.

Test cases to cover (at minimum):

- SCD2 dim: new natural key → insert as `is_current = TRUE,
  scd_version = 1`.
- SCD2 dim: same natural key, unchanged hash → no-op.
- SCD2 dim: same natural key, changed hash → expire old, insert new.
- SCD2 dim: row that already has an expired version + a new change
  → expire current, insert new, leave old expired row untouched.
- SCD1 dim: new natural key → insert.
- SCD1 dim: existing natural key, different attributes → overwrite.
- Fact load: null `community_area` → resolves to `dim_location` key 0
  (unknown), fact row **not** dropped.
- Fact load: re-running the same silver partition → upsert by
  `crime_id`, zero net new rows.
- Fact load: occurrence date in 1990 → still resolves a valid
  `dim_date` (verify `dim_date` seed range covers the historical
  backfill, or that the `0` row absorbs it).
- Workflow: silver→gold dims fails → facts job does **not** run
  (CONDITIONAL predicate).

---

## 4. Order of Execution

The dependency graph is:

```
Track 1 (RDS)  ─┐
                ├─→  Track 2 (DDL)  ─┐
                └─→  Track 4 (Glue Workflow Terraform)  ─┐
                                                          ├─→  Track 3 (Glue job code)  ─→  Track 5 (Tests)
                                                          │                                       │
                                                          └────────────── apply + smoke test ─────┘
```

A reasonable PR sequence:

1. **PR-A: RDS + secret + Glue JDBC connection** (Track 1). Apply,
   verify the Glue connection succeeds with the AWS-provided
   "Test Connection" action.
2. **PR-B: DDL bootstrap** (Track 2). Apply, verify the schemas
   exist and the seed rows are present via `psql` or a one-shot
   query Lambda.
3. **PR-C: Glue dims job** (Tracks 3 dims + 4 partial + 5 unit
   tests). Apply, manually start the dims job, verify `dw.dim_*`
   tables populate.
4. **PR-D: Glue facts job** (Tracks 3 facts + 4 remainder + 5 fact
   tests). Apply, run the full workflow, verify the `dimensional-design.md`
   §10.3 acceptance checklist passes against AWS.

Each PR is independently mergeable and apply-able. PR-A and PR-B
are pure infra and have no AWS-runtime risk beyond the RDS instance
itself.

---

## 5. Verification

End-state acceptance is `dimensional-design.md` §10.3:

- [ ] `fact_crime` loaded at incident grain with all conformed FKs
      populated.
- [ ] `dim_date` smart-keyed and prepopulated for 2018-01-01 through
      today.
- [ ] `dim_location` shows ≥ 2 SCD2 versions for at least one
      community area. **(Not satisfiable until source 3 lands —
      record as known-deferred.)**
- [ ] `dim_crime_type` shows ≥ 1 historical version. **(Not
      satisfiable until source 2 lands and an IUCR code goes
      inactive — record as known-deferred.)**
- [ ] All Q1-Q5 queries from `dimensional-design.md` §3.0 return
      non-empty, sensible answers when executed as SQL against `dw.*`
      via `psql`. **(Q2 needs source 4 for weather slice; Q4 needs
      source 3 for socioeconomics. Q1, Q3, Q5 are answerable today.)**
- [ ] No fact row dropped due to NULL FK.
- [ ] Re-running the daily ingest is idempotent.

Plus a smoke-test query that should pass on day one of `dw.*`:

```sql
SELECT dl.community_area, dct.primary_type, COUNT(*)
  FROM dw.fact_crime fc
  JOIN dw.dim_location  dl USING (location_key)
  JOIN dw.dim_crime_type dct USING (crime_type_key)
  JOIN dw.dim_date      dd  ON dd.date_key = fc.occurrence_date_key
 WHERE dd.year = 2024
 GROUP BY 1, 2
 ORDER BY 3 DESC
 LIMIT 10;
```

Should return the same primary-type top-10 we already verified in
silver via Athena (THEFT, BATTERY, CRIMINAL DAMAGE, ASSAULT, MOTOR
VEHICLE THEFT, …).

---

## 6. Open Questions Before Starting

Pulled from `dimensional-design.md` §10.2 and surfaced again here
because they shape the silver→gold work directly:

1. **Is `fact_arrest` in V1?** Decision affects whether
   `dim_arrestee` / `bridge_arrest_charge` are merely created
   (cheap, schema-only) or also loaded (requires source 5 first).
   **Recommendation:** create the tables in PR-B, defer loading
   until source 5 ships.
2. **How many socioeconomic snapshots will land in silver?** Drives
   how many SCD2 versions `dim_location` ends up with. **Recommendation:**
   plan for 3 snapshots (2018, 2021, 2024) per
   `dimensional-design.md` §10.2 Q2.
3. **Will the silver→gold job run as one Glue job or two?** This plan
   recommends two (dims, then facts) to make the FK-resolution
   dependency explicit at the workflow level rather than buried inside
   one job's control flow.
4. **Bootstrap DDL — Terraform `local-exec`, one-shot Lambda, or
   manual `psql`?** Recommendation: Lambda, for VPC-locality and
   auditable invocation history.
5. **What is the Glue worker size for the gold job?** Bronze→silver
   uses the project default. The dims job is small (≤ 100 K rows
   total); the facts job has 1.75 M rows of `chicago_crime` to
   resolve against ~thousands of dim rows. Defaults should be more
   than enough; revisit only if runtime exceeds the workflow timeout.

---

## 7. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| RDS endpoint unreachable from Glue (security-group or subnet misconfig) | Medium | Blocks all gold work | PR-A includes a Glue "Test Connection" run before merging. |
| SCD2 merge double-versions on re-run (writes a new version even when nothing changed) | Medium | Schema bloat, wrong "as-of" answers | Hash-based change detection (`scd_hash` column from `dimensional-design.md` §5). Test it (Track 5 case 2 & 3). |
| Fact rows dropped silently due to null FK | High if not coded for | Wrong totals | Mandatory null-coalesce step in the fact loader; Track 5 explicit test. |
| Glue job re-reads the silver sentinel partition (`_ingest_year = 9999`) and produces nonsense FKs | Medium | Garbage `dim_date` row 0 instead of real date | Reader **must** filter `WHERE _ingest_year != 9999` per `CLAUDE.md` Silver-Layer section. |
| RDS password rotation breaks the Glue job | Low | One-day outage | Glue reads from Secrets Manager at job start, not from a baked-in env var. Rotation is transparent. |
| Cost overrun — RDS left running 24/7 | Low | < $20/month at `db.t4g.micro` | Per `architecture.md` §9 cost table; acceptable for a course project. Add a budget alert if paranoid. |

---

## 8. What This Plan Does **Not** Cover

These are real and necessary, just not part of S3 silver → RDS gold:

- Adding the four remaining bronze→silver source modules
  (`architecture.md` §11 next-steps item 3).
- Replacing `AWSGlueServiceRole` with a tighter inline policy
  (PR #1 review Important #6 — deferred).
- The "row-count and referential-integrity sensor" at the end of the
  workflow (`architecture.md` §7 final DAG node). Optional V1.5 work.
- Anything BI-tier (dashboards, semantic layer, exports). The
  contract this slice meets is "RDS has correct dimensional data";
  what consumes that RDS is a separate slice.

---

## 9. Done Definition for This Slice

The silver→gold slice is "done" when:

1. `terraform apply` in a clean account stands up RDS + the silver→gold
   Glue jobs + the extended workflow with no manual steps.
2. The full daily workflow (EventBridge → bronze crawler → bronze→silver
   → silver crawler → silver→gold dims → silver→gold facts) runs end-to-end
   with status `COMPLETED`.
3. `dw.fact_crime` has 1.75 M rows for the current backfill window,
   all FKs resolve (no NULLs in FK columns), and re-running the
   workflow does not change the row count.
4. The smoke-test query in §5 returns the expected primary-type
   top-10 distribution.
5. The known-deferred acceptance items from §5 are documented in this
   file with a clear "blocked on source N" tag, so the next maintainer
   can pick them up without re-deriving the dependency map.
