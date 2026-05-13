# Terraform Infrastructure

The Terraform stack provisions the bronze ingest path **and** the bronze ->
silver Glue ETL slice:

- S3 raw data lake bucket (single bucket; `raw/`, `standardized/`, and
  `glue/` prefixes coexist for cost and IAM simplicity).
- Raw Chicago crime prefix: `raw/chicaho_crime/ingest_date=YYYY-MM-DD/`.
- Lambda function that fetches Chicago crime CSV data, plus the daily 02:00
  America/Chicago EventBridge Scheduler that invokes it.
- Glue Data Catalog databases: `data_warehouse_final_bronze` and
  `data_warehouse_final_silver`.
- Two Glue Crawlers (one per zone) with `TableLevelConfiguration=3` so each
  crawler registers **one logical table per source** (not one per
  `ingest_date=...` partition).
- Glue Job `data-warehouse-final-bronze-to-silver` (Glue 5.0, Spark 3.5)
  parameterised by `--source`. Today only `chicago_crime` is implemented;
  additional sources are added by appending to `var.glue_supported_sources`
  and dropping a handler module under
  `src/glue_jobs/bronze_to_silver/sources/`.
- Glue Workflow that chains: bronze crawler -> per-source job runs ->
  silver crawler.
- EventBridge Scheduler that calls `glue:StartWorkflowRun` daily at 03:30
  America/Chicago. We use EventBridge Scheduler (timezone-aware) rather
  than Glue's built-in cron (UTC-only).

File layout in this directory:

| File | Holds |
|---|---|
| `main.tf` | provider, locals, account-identity data source |
| `s3.tf` | bucket + bucket config + prefix markers (`raw/chicaho_crime/`, `standardized/`, `glue/scripts/`) |
| `lambda_chicago_crime.tf` | bronze fetch Lambda, IAM, scheduler |
| `glue.tf` | catalog DBs, IAM, log group, crawlers, job, workflow + triggers, EventBridge Scheduler |
| `variables.tf`, `outputs.tf`, `terraform.tfvars.example` | inputs/outputs |

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

# 2. Poll until COMPLETED. Expect ~5-10 minutes for the bronze crawler +
#    one chicago_crime job + the silver crawler on a cold start.
until [ "$(aws glue get-workflow-run --name "$WF" --run-id "$RUN_ID" \
  --query 'Run.Status' --output text)" = "COMPLETED" ]; do
  sleep 30
  aws glue get-workflow-run --name "$WF" --run-id "$RUN_ID" \
    --query 'Run.Statistics' --output table
done

# 3. Verify silver objects exist.
aws s3 ls "s3://$(terraform -chdir=terraform output -raw raw_bucket_name)/$(terraform -chdir=terraform output -raw silver_prefix)/chicago_crime/" --recursive | head
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
