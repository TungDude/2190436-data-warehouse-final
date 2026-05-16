# Pause Log — Project Wind-Down for Grading

**Paused on:** 2026-05-16 (Asia/Bangkok)
**Reason:** Project deliverable complete. AWS infrastructure is being held in place for grading, but all recurring schedules are turned off and the warehouse database is stopped to minimise idle cost while the dashboards remain viewable from SPICE cache.

Nothing was destroyed. Every paused service can be brought back by reverting the tfvars edit and running one `terraform apply`, plus a single `aws rds start-db-instance` for the database.

## What was paused

### 1. EventBridge schedulers (via Terraform)

`terraform/terraform.tfvars` now sets:

```hcl
fetch_schedule_enabled         = false
glue_workflow_schedule_enabled = false
quicksight_refresh_enabled     = false
```

> Note: `terraform.tfvars` is gitignored (it carries operator-specific values like the QuickSight admin ARN). The pause toggle pattern is mirrored in `terraform/terraform.tfvars.example` so the convention is discoverable in version control.

After `terraform apply`:

| Resource | Live state | Effect |
|---|---|---|
| `aws_scheduler_schedule.daily_fetch_chicago_crime` | `DISABLED` | Lambda no longer auto-fetches Chicago crime data at 02:00 America/Chicago. |
| `aws_scheduler_schedule.daily_glue_workflow` | `DISABLED` | Bronze→silver→gold Glue Workflow no longer kicks off at 03:30 America/Chicago. |
| `aws_quicksight_refresh_schedule.crime_analytics` | destroyed (count=0) | QuickSight no longer issues a daily SPICE FULL_REFRESH at 04:30 America/Chicago. The dataset itself (and the cached ~1.73M rows in SPICE) is intact. |

The scheduler resources themselves still exist in Terraform state and AWS — only their `state` field flipped from `ENABLED` to `DISABLED`. Re-enabling is a tfvars flip + apply.

### 2. RDS PostgreSQL instance (manual, outside Terraform)

```
aws --profile data-warehouse-final --region ap-southeast-1 \
  rds stop-db-instance --db-instance-identifier data-warehouse-final-dw
```

Verified state: `stopping` → will settle to `stopped`.

> ⚠️ **AWS auto-restarts a stopped RDS instance after 7 days.** While the project is in grading mode, re-run the `stop-db-instance` command weekly to keep the instance off. Re-stopping is idempotent and incurs no data risk; storage is preserved either way.

The instance, its data, parameter group, subnet group, security groups, Secrets Manager secret, and Glue JDBC Connection are all untouched. Terraform will report no drift on the database resource — RDS instance status is not tracked in state.

## What was deliberately *not* paused

| Resource | Why it stays running |
|---|---|
| **QuickSight Enterprise subscription** | Cannot be paused, only unsubscribed. Required for the grader to view the two dashboards. |
| **QuickSight dataset, data source, VPC connection, dashboards** | The grader needs them visible; SPICE keeps ~1.73M cached rows so dashboards continue to render with RDS stopped. |
| **S3 raw bucket + all standardized/gold objects** | Storage-only cost (pennies). Required artefact. |
| **Glue Data Catalog (bronze + silver databases, tables)** | Storage-only cost. Required artefact. |
| **Lambda + Glue Jobs (definitions)** | Cost is zero when idle; only paid per invocation. |
| **VPC Interface endpoints** (`secretsmanager`, `logs`, `sts`, `glue`) | Largest idle cost (~$22/mo each across the default-VPC subnets), but they are infrastructure pieces, not "services running." Left in place per the user's instruction to avoid destroy. Tear them down with `terraform destroy -target=aws_vpc_endpoint.{secretsmanager,logs,sts,glue}` if extra savings are needed later. |
| **Secrets Manager secret (`data-warehouse-final-rds-master`)** | ~$0.40/mo. Needed when RDS is brought back. |

## How to resume the pipeline

```bash
# 1. Re-enable all schedulers in Terraform
cd terraform
# Edit terraform.tfvars — flip the three *_enabled flags back to true,
# or delete the "Project paused on 2026-05-16" block entirely.
terraform apply

# 2. Start RDS back up
aws --profile data-warehouse-final --region ap-southeast-1 \
  rds start-db-instance --db-instance-identifier data-warehouse-final-dw

# Wait ~5 minutes for the instance to reach 'available' before the
# 03:30 America/Chicago Glue workflow fires.
```

Re-applying the QuickSight refresh schedule recreates it from scratch (same `schedule_id`, same daily 04:30 America/Chicago slot) — no state migration required.

## Verification snapshot (2026-05-16)

| Check | Command | Result |
|---|---|---|
| Lambda schedule | `aws scheduler get-schedule --name data-warehouse-final-fetch-chicago-crime-daily --query State` | `DISABLED` |
| Glue schedule | `aws scheduler get-schedule --name data-warehouse-final-glue-workflow-daily --query State` | `DISABLED` |
| SPICE refresh | `aws quicksight list-refresh-schedules --aws-account-id 238027390687 --data-set-id data-warehouse-final-crime-analytics --query RefreshSchedules` | `[]` |
| RDS status | `aws rds describe-db-instances --db-instance-identifier data-warehouse-final-dw --query 'DBInstances[0].DBInstanceStatus'` | `stopping` |
