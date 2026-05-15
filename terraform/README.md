# Terraform Infrastructure

The Terraform stack provisions the full bronze -> silver -> gold pipeline:

- **Bronze ingest** — S3 raw data lake bucket; Lambda + EventBridge
  Scheduler for daily Chicago Crime fetches.
- **Silver Glue ETL** — Glue Catalog DBs, crawlers, per-source PySpark
  jobs, workflow + triggers.
- **Gold tier** — Amazon RDS for PostgreSQL 16 inside the default VPC; a
  one-shot DDL bootstrap Lambda that applies `sql/dw_schema.sql` and
  `sql/dw_seed.sql` to RDS at apply-time; AWS Glue JDBC Connection;
  two silver -> gold PySpark Glue Jobs (`dims` then `facts`) chained
  onto the existing workflow.
- **BI tier** - optional QuickSight VPC connection, PostgreSQL data source,
  SPICE dataset, daily refresh schedule, and two Terraform-managed dashboards.

The single S3 bucket carries every prefix (`raw/`, `standardized/`,
`glue/scripts/`, `sql/`) for cost and IAM simplicity.

File layout in this directory:

| File | Holds |
|---|---|
| `main.tf` | provider, locals, required providers (aws + archive + null + random) |
| `s3.tf` | bucket + bucket config + prefix markers |
| `lambda_chicago_crime.tf` | bronze fetch Lambda + scheduler |
| `glue.tf` | bronze + silver catalog DBs, IAM, log group, crawlers, bronze->silver job(s), workflow + triggers, EventBridge Scheduler |
| `rds.tf` | RDS Postgres 16, Secrets Manager, db subnet group, Glue JDBC Connection, security groups |
| `vpc_endpoints.tf` | S3 Gateway + Secrets Manager/Logs Interface endpoints so in-VPC Lambda + Glue can reach AWS APIs |
| `lambda_dw_bootstrap.tf` | one-shot Lambda that applies SQL DDL to RDS, layer build for psycopg[binary] |
| `silver_to_gold.tf` | silver->gold dims + facts Glue Jobs, workflow extension triggers |
| `quicksight.tf` | optional QuickSight VPC connection, RDS data source, SPICE dataset, refresh schedule, and dashboards |
| `variables.tf`, `outputs.tf` | inputs/outputs |

## Local validation (no AWS apply)

The Glue slice ships with full local validation. None of these commands
require an AWS apply.

```sh
cd terraform
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
```

A full `terraform plan` (with `AWS_PROFILE=data-warehouse-final`) on top of
the existing state should show:

- **No diff** on `aws_s3_bucket.raw`, `aws_lambda_function.fetch_chicago_crime`,
  `aws_scheduler_schedule.daily_fetch_chicago_crime`, and the IAM resources
  that moved between files (the file split in this PR is purely cosmetic).
- **Adds only** for `aws_s3_object.silver_prefix`,
  `aws_s3_object.glue_scripts_prefix`, `aws_s3_object.bronze_to_silver_script`,
  the single `aws_s3_object.bronze_to_silver_libs` zip object, one
  `aws_glue_job.bronze_to_silver["<source>"]` and one
  `aws_cloudwatch_log_group.glue_bronze_to_silver["<source>"]` per
  `var.glue_supported_sources` element, the Glue catalog DBs, both crawlers,
  the workflow + triggers, the Glue IAM role + policies, the workflow-starter
  IAM role, and `aws_scheduler_schedule.daily_glue_workflow`.

Java 17 is required for Spark 3.5 if you want to run the local pytest suite
(see `requirements-dev.txt`). The repo's `flake.nix` provides a JDK; you can
also install your platform's `openjdk-17`.

## Apply (when you are ready)

```sh
export AWS_PROFILE=data-warehouse-final
terraform init
terraform plan
terraform apply
```

**SSL note** — `rds.tf` now ships an `aws_db_parameter_group` with
`rds.force_ssl=1` attached to the RDS instance. Because `aws_db_instance.dw`
already has `apply_immediately = true`, the **first** apply after this
change reboots RDS **synchronously during `terraform apply`** (typically
1-3 minutes for db.t4g.micro). The PostgreSQL JDBC driver and our
silver→gold Glue jobs honour `sslmode=require` automatically, so no
application change is needed. However:

- The reboot pauses any in-flight Glue job that holds a JDBC session.
- Apply outside the 03:30 America/Chicago Glue Workflow start time, or
  disable `aws_scheduler_schedule.daily_glue_workflow` before applying.
- After apply, `psql ... -c "SHOW rds.force_ssl"` should return `1`.

## QuickSight dashboards

QuickSight is opt-in because the account must already be subscribed and the
Terraform stack cannot infer the QuickSight author principal.

1. Subscribe the account to QuickSight in `aws_region` if it is not already
   enabled.
2. Find the QuickSight principal ARN for the author/user or group that should
   own the assets. User ARNs look like
   `arn:aws:quicksight:ap-southeast-1:238027390687:user/default/<username>`.
3. Set these variables and apply:

```hcl
quicksight_enabled             = true
quicksight_admin_principal_arn = "arn:aws:quicksight:ap-southeast-1:238027390687:user/default/<username>"
```

Terraform will create:

- `Chicago Crime Overview`: total-incidents KPI, arrest-rate KPI (calculated
  `sum(is_arrest)*100/sum(incident_count)`), monthly trend line, primary-type
  donut, and a geospatial point map coloured by community area. Two filter
  controls — occurrence-date range and community-area multi-select.
- `Chicago Crime Detail`: day/hour heatmap, weather-vs-incidents scatter
  (avg temperature × avg precipitation, sized by incident count, coloured by
  primary type), monthly arrest trend by district, and a community×crime-type
  table augmented with arrest rate. Three controls — an SCD2 `AsOfDate`
  parameter (filters fact rows to the `dim_location` *and* `dim_crime_type`
  SCD2 versions active on that date), an occurrence-date range filter, and a
  domestic-flag dropdown.
- a daily SPICE full refresh at `quicksight_refresh_time` (default `04:30`
  America/Chicago — one hour after the 03:30 gold Glue workflow start).

The QuickSight data source authenticates against the master credentials in
AWS Secrets Manager via a resource-based secret policy that allows the
`quicksight.amazonaws.com` service principal `GetSecretValue` on the secret
ARN. No credentials are inlined into Terraform state.

The Detail dashboard's "Domestic" dropdown lists the raw integer values
`0` (not domestic) and `1` (domestic) — `dim_crime_flags.is_domestic` is
cast to INTEGER in the SPICE SQL so it sums cleanly in KPIs and the
heatmap. Treat the dropdown labels as boolean: pick `1` for domestic-only,
`0` for non-domestic-only, or leave both selected for all incidents.

The Glue Workflow runs once per day at 03:30 America/Chicago (90 minutes
after the chicago_crime fetch Lambda). To trigger an ad-hoc run:

```sh
aws glue start-workflow-run --name $(terraform output -raw glue_workflow_name)
```

## Smoke test the workflow on first apply

The Glue Workflow's entry trigger is `ON_DEMAND` and is started by EventBridge
Scheduler via `glue:StartWorkflowRun`. Before relying on the daily schedule,
confirm an end-to-end run works:

```sh
export AWS_PROFILE=data-warehouse-final
WF=$(terraform -chdir=terraform output -raw glue_workflow_name)

# 1. Kick the workflow.
RUN_ID=$(aws glue start-workflow-run --name "$WF" --query 'RunId' --output text)

# 2. Poll until COMPLETED. Expect ~15-25 minutes on cold start: bronze
#    crawler + per-source bronze->silver jobs + silver crawler +
#    silver->gold dims + silver->gold facts.
until [ "$(aws glue get-workflow-run --name "$WF" --run-id "$RUN_ID" \
  --query 'Run.Status' --output text)" = "COMPLETED" ]; do
  sleep 30
  aws glue get-workflow-run --name "$WF" --run-id "$RUN_ID" \
    --query 'Run.Statistics' --output table
done

# 3. Verify silver objects exist.
aws s3 ls "s3://$(terraform -chdir=terraform output -raw raw_bucket_name)/$(terraform -chdir=terraform output -raw silver_prefix)/chicago_crime/" --recursive | head

# 4. Verify gold rows in RDS (run from a host inside the VPC, or via a
#    bastion / Session Manager port forward).
psql -h "$(terraform -chdir=terraform output -raw rds_endpoint)" -U dw_admin -d dw \
  -c "SELECT 'dim_date' tbl, COUNT(*) n FROM dw.dim_date
      UNION ALL SELECT 'dim_time_of_day', COUNT(*) FROM dw.dim_time_of_day
      UNION ALL SELECT 'dim_location', COUNT(*) FROM dw.dim_location
      UNION ALL SELECT 'dim_crime_type', COUNT(*) FROM dw.dim_crime_type
      UNION ALL SELECT 'fact_crime', COUNT(*) FROM dw.fact_crime;"
```

If the workflow status is `ERROR` at any node, inspect the run graph:

```sh
aws glue get-workflow-run --name "$WF" --run-id "$RUN_ID" --include-graph \
  --query 'Run.Graph.Nodes[?Type==`JOB` || Type==`CRAWLER`].{Name:Name,Type:Type,Status:JobDetails.JobRuns[0].JobRunState || CrawlerDetails.Crawls[0].State}' \
  --output table
```

## Backfill

After applying Terraform, use the backfill script to load historical data in
monthly chunks. The Chicago crime source excludes the most recent seven days, so
the default end date is eight days before the current local date.

```powershell
.\scripts\backfill_chicago_crime.ps1 `
  -StartDate 2019-01-01 `
  -Profile data-warehouse-final `
  -Region ap-southeast-1
```
