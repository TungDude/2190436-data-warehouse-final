# Terraform Infrastructure

This Terraform stack creates the first ingestion slice:

- S3 raw data lake bucket.
- Raw Chicago crime prefix: `raw/chicaho_crime/ingest_date=YYYY-MM-DD/`.
- Lambda function that fetches Chicago crime CSV data.
- EventBridge Scheduler that invokes the Lambda daily at 2 AM.

Before running Terraform, read `.agents/AGENTS.local.md` or
`.claude/CLAUDE.local.md` and use the configured AWS profile.

Example:

```powershell
$env:AWS_PROFILE = "data-warehouse-final"
terraform init
terraform plan
terraform apply
```

The default schedule timezone is `America/Chicago`.

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
