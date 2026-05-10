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
  the per-file `aws_s3_object.bronze_to_silver_extra_py["..."]` entries, the
  Glue catalog/crawler/job/workflow/trigger resources, the Glue IAM role
  + policies, the Glue CloudWatch log group, the workflow-starter IAM role,
  and `aws_scheduler_schedule.daily_glue_workflow`.

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
