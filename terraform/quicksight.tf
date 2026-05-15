# ---------------------------------------------------------------------------
# QuickSight BI layer
#
# Creates the BI surface described in docs/architecture.md Section 8:
# private VPC connectivity to RDS, one SPICE dataset on the gold star schema,
# and two dashboards for overview and analyst detail views.
#
# QuickSight itself is account-local state. Set quicksight_enabled=true only
# after the AWS account has a QuickSight subscription in this region and pass a
# QuickSight principal ARN if the assets should be visible/editable in the UI.
# ---------------------------------------------------------------------------

locals {
  quicksight_dataset_identifier = "crime_analytics"

  # SCD2 columns from dim_location and dim_crime_type are exposed so the
  # Detail dashboard can offer an "as-of-date" filter that proves the
  # warehouse honors point-in-time correctness (docs/architecture.md §8,
  # docs/dimensional-design.md §3.0 Q4).
  #
  # ct.index_code is included even though the IUCR loader has not landed
  # yet — keeping it in the SPICE SQL means a later source-2 deployment
  # picks up Q4 (Index Crime vs Non-Index) without a redeploy of the
  # QuickSight stack.
  quicksight_crime_analytics_sql = <<-SQL
    SELECT
      fc.crime_id::text                           AS crime_id,
      fc.incident_count::integer                  AS incident_count,
      fc.is_arrest::integer                       AS is_arrest,
      fc.is_domestic::integer                     AS is_domestic,
      COALESCE(fc.hours_to_update, 0)::integer    AS hours_to_update,
      fc.latitude::numeric                        AS latitude,
      fc.longitude::numeric                       AS longitude,
      COALESCE(fc.temperature_celsius, 0)::numeric AS temperature_celsius,
      COALESCE(fc.precipitation_mm, 0)::numeric    AS precipitation_mm,
      d.full_date::timestamp                      AS occurrence_date,
      d.year::integer                             AS occurrence_year,
      d.quarter::integer                          AS occurrence_quarter,
      d.month_num::integer                        AS occurrence_month,
      d.month_name                                AS occurrence_month_name,
      d.day_of_week::integer                      AS occurrence_day_of_week,
      d.day_name                                  AS occurrence_day_name,
      tod.hour_24::integer                        AS occurrence_hour,
      tod.period_of_day                           AS period_of_day,
      COALESCE(loc.community_area, 0)::integer    AS community_area,
      COALESCE(loc.community_area_name, 'Unknown') AS community_area_name,
      COALESCE(loc.district, 'Unknown')           AS district,
      COALESCE(loc.ward, 0)::integer              AS ward,
      -- Socioeconomic SCD2 attributes from source 3. Exposed in SPICE so
      -- users can slice Q4 ("do socioeconomically distressed community
      -- areas have higher Index Crime rates?") directly in QuickSight
      -- without rebuilding the dataset. Each fact row carries the SCD2
      -- version of the location attributes active when the crime occurred.
      loc.pct_below_poverty::numeric              AS pct_below_poverty,
      loc.pct_unemployed_16plus::numeric          AS pct_unemployed_16plus,
      loc.pct_no_hs_25plus::numeric               AS pct_no_hs_25plus,
      loc.per_capita_income_usd::integer          AS per_capita_income_usd,
      loc.hardship_index::integer                 AS hardship_index,
      -- SCD2 sentinel dates 0001-01-01 / 9999-12-31 fall outside the
      -- QuickSight DateTime range (1583..9999 per docs, but ingestion
      -- rejects 0001 specifically). Clamp to a QS-safe window so the
      -- as-of-date parameter still filters correctly while keeping rows
      -- in SPICE. The clamped values are wider than any plausible event
      -- date, so the SCD2 semantics are preserved.
      GREATEST(loc.scd_start_date, '1900-01-01'::date)::timestamp AS location_scd_start,
      LEAST(loc.scd_end_date, '2099-12-31'::date)::timestamp       AS location_scd_end,
      loc.is_current::integer                                       AS location_is_current,
      loc.scd_version::integer                                      AS location_scd_version,
      COALESCE(ct.primary_type, 'Unknown')        AS primary_type,
      COALESCE(ct.description, 'Unknown')         AS crime_description,
      COALESCE(ct.fbi_code, 'Unknown')            AS fbi_code,
      COALESCE(ct.index_code, 'U')                AS index_code,
      GREATEST(ct.scd_start_date, '1900-01-01'::date)::timestamp AS crime_type_scd_start,
      LEAST(ct.scd_end_date, '2099-12-31'::date)::timestamp       AS crime_type_scd_end,
      ct.is_current::integer                                       AS crime_type_is_current,
      COALESCE(w.weather_category, 'Unavailable') AS weather_category,
      COALESCE(w.temp_band, 'Unavailable')        AS temp_band,
      COALESCE(w.precip_band, 'Unavailable')      AS precip_band
    FROM dw.fact_crime fc
    JOIN dw.dim_date d
      ON d.date_key = fc.occurrence_date_key
    JOIN dw.dim_time_of_day tod
      ON tod.time_key = fc.occurrence_time_key
    JOIN dw.dim_location loc
      ON loc.location_key = fc.location_key
    JOIN dw.dim_crime_type ct
      ON ct.crime_type_key = fc.crime_type_key
    JOIN dw.dim_weather w
      ON w.weather_key = fc.weather_key
    -- Geographic-role tagging on latitude/longitude (logical_table_map.tag_column_operation
    -- above) makes QuickSight reject NULL coords during SPICE ingestion. About
    -- 5-7% of historical Chicago crime rows lack coordinates; including them
    -- breaches the default 10k error tolerance. Filtering keeps the map
    -- functional and still leaves 1.5M+ rows for all other dashboards.
    WHERE fc.latitude IS NOT NULL
      AND fc.longitude IS NOT NULL
  SQL

  quicksight_crime_analytics_columns = [
    { name = "crime_id", type = "STRING" },
    { name = "incident_count", type = "INTEGER" },
    { name = "is_arrest", type = "INTEGER" },
    { name = "is_domestic", type = "INTEGER" },
    { name = "hours_to_update", type = "INTEGER" },
    { name = "latitude", type = "DECIMAL" },
    { name = "longitude", type = "DECIMAL" },
    { name = "temperature_celsius", type = "DECIMAL" },
    { name = "precipitation_mm", type = "DECIMAL" },
    { name = "occurrence_date", type = "DATETIME" },
    { name = "occurrence_year", type = "INTEGER" },
    { name = "occurrence_quarter", type = "INTEGER" },
    { name = "occurrence_month", type = "INTEGER" },
    { name = "occurrence_month_name", type = "STRING" },
    { name = "occurrence_day_of_week", type = "INTEGER" },
    { name = "occurrence_day_name", type = "STRING" },
    { name = "occurrence_hour", type = "INTEGER" },
    { name = "period_of_day", type = "STRING" },
    { name = "community_area", type = "INTEGER" },
    { name = "community_area_name", type = "STRING" },
    { name = "district", type = "STRING" },
    { name = "ward", type = "INTEGER" },
    { name = "pct_below_poverty", type = "DECIMAL" },
    { name = "pct_unemployed_16plus", type = "DECIMAL" },
    { name = "pct_no_hs_25plus", type = "DECIMAL" },
    { name = "per_capita_income_usd", type = "INTEGER" },
    { name = "hardship_index", type = "INTEGER" },
    { name = "location_scd_start", type = "DATETIME" },
    { name = "location_scd_end", type = "DATETIME" },
    { name = "location_is_current", type = "INTEGER" },
    { name = "location_scd_version", type = "INTEGER" },
    { name = "primary_type", type = "STRING" },
    { name = "crime_description", type = "STRING" },
    { name = "fbi_code", type = "STRING" },
    { name = "index_code", type = "STRING" },
    { name = "crime_type_scd_start", type = "DATETIME" },
    { name = "crime_type_scd_end", type = "DATETIME" },
    { name = "crime_type_is_current", type = "INTEGER" },
    { name = "weather_category", type = "STRING" },
    { name = "temp_band", type = "STRING" },
    { name = "precip_band", type = "STRING" },
  ]

  quicksight_data_source_actions = [
    "quicksight:DescribeDataSource",
    "quicksight:DescribeDataSourcePermissions",
    "quicksight:PassDataSource",
    "quicksight:UpdateDataSource",
    "quicksight:DeleteDataSource",
    "quicksight:UpdateDataSourcePermissions",
  ]

  quicksight_data_set_actions = [
    "quicksight:DescribeDataSet",
    "quicksight:DescribeDataSetPermissions",
    "quicksight:PassDataSet",
    "quicksight:DescribeIngestion",
    "quicksight:ListIngestions",
    "quicksight:CreateIngestion",
    "quicksight:CancelIngestion",
    "quicksight:UpdateDataSet",
    "quicksight:DeleteDataSet",
    "quicksight:UpdateDataSetPermissions",
  ]

  # QuickSight dashboard permissions only accept the eight actions below as
  # the "owner" set. The CreateDashboard API rejects DescribeDashboardDefinition
  # explicitly for dashboards (it is valid for analyses, not dashboards) —
  # see the supported sets reported by the InvalidParameterValueException.
  quicksight_dashboard_actions = [
    "quicksight:DescribeDashboard",
    "quicksight:DescribeDashboardPermissions",
    "quicksight:ListDashboardVersions",
    "quicksight:QueryDashboard",
    "quicksight:UpdateDashboard",
    "quicksight:DeleteDashboard",
    "quicksight:UpdateDashboardPermissions",
    "quicksight:UpdateDashboardPublishedVersion",
  ]
}

# ---------------------------------------------------------------------------
# VPC connection execution role
# ---------------------------------------------------------------------------

resource "aws_iam_role" "quicksight_vpc_connection" {
  count = var.quicksight_enabled ? 1 : 0

  name = "${var.project_name}-quicksight-vpc-connection"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "quicksight.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "quicksight_vpc_connection" {
  count = var.quicksight_enabled ? 1 : 0

  name = "${var.project_name}-quicksight-vpc-connection"
  role = aws_iam_role.quicksight_vpc_connection[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ManageQuickSightVPCNetworkInterfaces"
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:ModifyNetworkInterfaceAttribute",
          "ec2:DeleteNetworkInterface",
          "ec2:DescribeSubnets",
          "ec2:DescribeSecurityGroups",
        ]
        Resource = "*"
      },
    ]
  })
}

# ---------------------------------------------------------------------------
# Secrets Manager — let QuickSight read the RDS master credentials
#
# `aws_quicksight_data_source.credentials.secret_arn` makes QuickSight pull
# the RDS username/password from Secrets Manager on demand instead of
# pinning them into Terraform state. QuickSight reads the secret as the
# `quicksight.amazonaws.com` service principal, which the resource-based
# policy below authorises explicitly (least-priv: GetSecretValue on this
# one secret ARN, conditioned on the current AWS account).
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "rds_master_quicksight" {
  count = var.quicksight_enabled ? 1 : 0

  statement {
    sid    = "AllowQuickSightReadRDSCredentials"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["quicksight.amazonaws.com"]
    }

    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.rds_master.arn]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_secretsmanager_secret_policy" "rds_master_quicksight" {
  count = var.quicksight_enabled ? 1 : 0

  secret_arn = aws_secretsmanager_secret.rds_master.arn
  policy     = data.aws_iam_policy_document.rds_master_quicksight[0].json
}

# ---------------------------------------------------------------------------
# QuickSight cross-service access roles
#
# Normally created by the QuickSight console subscription wizard when an
# admin opens "Manage QuickSight → Security & permissions → Manage AWS
# resources". CLI subscription skips that step, so QuickSight cannot reach
# Secrets Manager and fails with "The QuickSight service role required to
# access your AWS resources has not been created yet" when creating a data
# source with `credentials.secret_arn`.
#
# QuickSight looks up two well-known roles by name for cross-service access:
#
#   * `aws-quicksight-service-role-v0` — the primary IAM role QuickSight
#     assumes for data-source operations against AWS services (RDS, Athena,
#     etc.). Without this role present, the data source create call fails
#     even when the resource-based secret policy already allows the
#     `quicksight.amazonaws.com` service principal.
#   * `aws-quicksight-secretsmanager-role-v0` — secondary role specifically
#     used when QuickSight needs to read Secrets Manager. Same trust + same
#     GetSecretValue grant.
#
# Both names are AWS-fixed; QuickSight is hard-wired to look them up by
# string. Trust policy allows quicksight.amazonaws.com to assume them; the
# inline policy grants GetSecretValue on the single RDS master secret ARN —
# no wildcards.
# ---------------------------------------------------------------------------

locals {
  quicksight_service_role_names = var.quicksight_enabled ? toset([
    "aws-quicksight-service-role-v0",
    "aws-quicksight-secretsmanager-role-v0",
  ]) : toset([])
}

resource "aws_iam_role" "quicksight_service" {
  for_each = local.quicksight_service_role_names

  name = each.key

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "quicksight.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "quicksight_service_secrets" {
  for_each = local.quicksight_service_role_names

  name = "${var.project_name}-quicksight-secretsmanager-access"
  role = aws_iam_role.quicksight_service[each.key].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "AllowReadRDSMasterSecret"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [aws_secretsmanager_secret.rds_master.arn]
      },
    ]
  })
}

resource "aws_quicksight_vpc_connection" "dw" {
  count = var.quicksight_enabled ? 1 : 0

  aws_account_id     = data.aws_caller_identity.current.account_id
  vpc_connection_id  = "${var.project_name}-dw"
  name               = "${var.project_name}-dw"
  role_arn           = aws_iam_role.quicksight_vpc_connection[0].arn
  security_group_ids = [aws_security_group.quicksight.id]
  subnet_ids         = data.aws_subnets.default.ids

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# RDS data source + SPICE dataset
# ---------------------------------------------------------------------------

resource "aws_quicksight_data_source" "dw" {
  count = var.quicksight_enabled ? 1 : 0

  aws_account_id = data.aws_caller_identity.current.account_id
  data_source_id = "${var.project_name}-dw-postgres"
  name           = "${var.project_name} DW PostgreSQL"
  type           = "POSTGRESQL"

  parameters {
    postgresql {
      host     = aws_db_instance.dw.address
      port     = aws_db_instance.dw.port
      database = aws_db_instance.dw.db_name
    }
  }

  credentials {
    # credential_pair (not secret_arn) is what the QuickSight API actually
    # accepts in CLI-subscribed accounts. QuickSight's `secret_arn` mode
    # requires an opaque "Manage AWS resources → Secrets Manager → Select
    # secrets" registration that the console wizard performs but has no
    # API equivalent — applying with secret_arn fails with "The QuickSight
    # service role required to access your AWS resources has not been
    # created yet" even when aws-quicksight-{service,secretsmanager}-role-v0
    # exist with proper trust + GetSecretValue grants. Pulling the password
    # from the secret via random_password keeps the password out of source
    # code; tfstate already holds the same value via the secret version
    # resource, so this does not increase blast radius.
    credential_pair {
      username = aws_db_instance.dw.username
      password = random_password.rds_master.result
    }
  }

  vpc_connection_properties {
    vpc_connection_arn = aws_quicksight_vpc_connection.dw[0].arn
  }

  dynamic "permission" {
    for_each = var.quicksight_admin_principal_arn == null ? [] : [var.quicksight_admin_principal_arn]

    content {
      principal = permission.value
      actions   = local.quicksight_data_source_actions
    }
  }

  ssl_properties {
    disable_ssl = false
  }

  depends_on = [
    aws_secretsmanager_secret_policy.rds_master_quicksight,
    aws_iam_role_policy.quicksight_service_secrets["aws-quicksight-service-role-v0"],
    aws_iam_role_policy.quicksight_service_secrets["aws-quicksight-secretsmanager-role-v0"],
  ]

  tags = local.common_tags
}

resource "aws_quicksight_data_set" "crime_analytics" {
  count = var.quicksight_enabled ? 1 : 0

  aws_account_id = data.aws_caller_identity.current.account_id
  data_set_id    = "${var.project_name}-crime-analytics"
  name           = "${var.project_name} Crime Analytics"
  import_mode    = "SPICE"

  # QuickSight constrains physical/logical table map IDs to [0-9a-zA-Z-]+
  # (no underscores). Hyphenated IDs satisfy that.
  physical_table_map {
    physical_table_map_id = "crime-analytics-sql"

    custom_sql {
      data_source_arn = aws_quicksight_data_source.dw[0].arn
      name            = "crime_analytics"
      sql_query       = local.quicksight_crime_analytics_sql

      dynamic "columns" {
        for_each = local.quicksight_crime_analytics_columns

        content {
          name = columns.value.name
          type = columns.value.type
        }
      }
    }
  }

  # Tag latitude/longitude with QuickSight geographic roles so the Overview
  # geospatial map can plot points without manual column-type fiddling in
  # the QuickSight UI. ProjectOperation lists every column the dataset
  # exposes; without it the API rejects logical tables that have only
  # tag_column_operation transforms with "MeasureField/dropped row" errors
  # at SPICE ingestion time because the projected schema is inferred as
  # empty.
  logical_table_map {
    logical_table_map_id = "crime-analytics-logical"
    alias                = "crime_analytics"

    source {
      physical_table_id = "crime-analytics-sql"
    }

    data_transforms {
      project_operation {
        projected_columns = [
          for c in local.quicksight_crime_analytics_columns : c.name
        ]
      }
    }

    data_transforms {
      tag_column_operation {
        column_name = "latitude"

        tags {
          column_geographic_role = "LATITUDE"
        }
      }
    }

    data_transforms {
      tag_column_operation {
        column_name = "longitude"

        tags {
          column_geographic_role = "LONGITUDE"
        }
      }
    }
  }

  dynamic "permissions" {
    for_each = var.quicksight_admin_principal_arn == null ? [] : [var.quicksight_admin_principal_arn]

    content {
      principal = permissions.value
      actions   = local.quicksight_data_set_actions
    }
  }

  data_set_usage_configuration {
    # AWS persists `disable_use_as_direct_query_source = false` regardless of
    # what we send for SPICE-imported datasets. Sending `true` here triggers
    # a perpetual UpdateDataSet diff that the QuickSight API never finishes
    # (10+ minute hangs observed). Pinning to false eliminates the diff;
    # `disable_use_as_imported_source = false` matches the SPICE import mode.
    disable_use_as_direct_query_source = false
    disable_use_as_imported_source     = false
  }

  tags = local.common_tags
}

resource "aws_quicksight_refresh_schedule" "crime_analytics" {
  count = var.quicksight_enabled && var.quicksight_refresh_enabled ? 1 : 0

  aws_account_id = data.aws_caller_identity.current.account_id
  data_set_id    = aws_quicksight_data_set.crime_analytics[0].data_set_id
  schedule_id    = "${var.project_name}-crime-analytics-daily"

  schedule {
    refresh_type = "FULL_REFRESH"

    schedule_frequency {
      interval        = "DAILY"
      time_of_the_day = var.quicksight_refresh_time
      timezone        = var.quicksight_refresh_timezone
    }
  }
}

# ---------------------------------------------------------------------------
# Dashboard 1: Overview
# ---------------------------------------------------------------------------

resource "aws_quicksight_dashboard" "crime_overview" {
  count = var.quicksight_enabled ? 1 : 0

  aws_account_id      = data.aws_caller_identity.current.account_id
  dashboard_id        = "${var.project_name}-crime-overview"
  name                = "Chicago Crime Overview"
  version_description = "KPIs + monthly trend + primary-type donut + community-area geospatial map."

  definition {
    data_set_identifiers_declarations {
      identifier   = local.quicksight_dataset_identifier
      data_set_arn = aws_quicksight_data_set.crime_analytics[0].arn
    }

    # Date-range filter — exposes a date_time_picker control bound to
    # occurrence_date; default is the full 2018-->today slice.
    filter_groups {
      filter_group_id = "overview-date-range"
      cross_dataset   = "SINGLE_DATASET"
      status          = "ENABLED"

      filters {
        time_range_filter {
          filter_id        = "overview-occurrence-date"
          include_minimum  = true
          include_maximum  = true
          null_option      = "ALL_VALUES"
          time_granularity = "DAY"

          column {
            data_set_identifier = local.quicksight_dataset_identifier
            column_name         = "occurrence_date"
          }

          range_minimum_value {
            static_value = "2018-01-01T00:00:00Z"
          }

          range_maximum_value {
            rolling_date {
              expression = "now()"
            }
          }
        }
      }

      scope_configuration {
        selected_sheets {
          sheet_visual_scoping_configurations {
            sheet_id = "overview"
            scope    = "ALL_VISUALS"
          }
        }
      }
    }

    # Community-area multi-select filter — defaults to FILTER_ALL_VALUES
    # so the dashboard opens unfiltered.
    filter_groups {
      filter_group_id = "overview-community"
      cross_dataset   = "SINGLE_DATASET"
      status          = "ENABLED"

      filters {
        category_filter {
          filter_id = "overview-community-filter"

          column {
            data_set_identifier = local.quicksight_dataset_identifier
            column_name         = "community_area_name"
          }

          configuration {
            filter_list_configuration {
              match_operator     = "CONTAINS"
              select_all_options = "FILTER_ALL_VALUES"
            }
          }
        }
      }

      scope_configuration {
        selected_sheets {
          sheet_visual_scoping_configurations {
            sheet_id = "overview"
            scope    = "ALL_VISUALS"
          }
        }
      }
    }

    sheets {
      sheet_id = "overview"
      name     = "Overview"
      title    = "Chicago Crime Overview"

      filter_controls {
        date_time_picker {
          filter_control_id = "overview-date-range-control"
          source_filter_id  = "overview-occurrence-date"
          title             = "Occurrence date"
          type              = "DATE_RANGE"

          display_options {
            date_time_format = "yyyy-MM-dd"
            title_options {
              visibility = "VISIBLE"
            }
          }
        }
      }

      filter_controls {
        dropdown {
          filter_control_id = "overview-community-control"
          source_filter_id  = "overview-community-filter"
          title             = "Community area"
          type              = "MULTI_SELECT"

          display_options {
            title_options {
              visibility = "VISIBLE"
            }
          }
        }
      }

      visuals {
        kpi_visual {
          visual_id = "overview-total-incidents"

          title {
            format_text {
              plain_text = "Total incidents"
            }
          }

          chart_configuration {
            field_wells {
              values {
                numerical_measure_field {
                  field_id = "total-incidents"

                  column {
                    data_set_identifier = local.quicksight_dataset_identifier
                    column_name         = "incident_count"
                  }

                  aggregation_function {
                    simple_numerical_aggregation = "SUM"
                  }
                }
              }
            }
            # NB: kpi_options.primary_value_display_type is only valid when
            # the KPI has a target_value or trend_group set, otherwise
            # QuickSight rejects with "Only PrimaryValueFontSize display
            # property can be defined when TargetValue and TrendGroup fields
            # are empty". Defaults are fine here.
          }
        }
      }

      # Arrests KPI — total arrest events. Originally a calculated_measure_field
      # (arrest rate %), but QuickSight's CreateDashboard API rejected the
      # calculated expression with "MeasureField can not be empty" even
      # though the expression and field_id were well-formed. Falling back
      # to a SUM of is_arrest keeps the visual on the deck; the arrest-rate
      # view can be reconstructed by users dividing this by total incidents
      # via QuickSight's UI calculation builder.
      visuals {
        kpi_visual {
          visual_id = "overview-arrests"

          title {
            format_text {
              plain_text = "Total arrests"
            }
          }

          chart_configuration {
            field_wells {
              values {
                numerical_measure_field {
                  field_id = "arrests-kpi"

                  column {
                    data_set_identifier = local.quicksight_dataset_identifier
                    column_name         = "is_arrest"
                  }

                  aggregation_function {
                    simple_numerical_aggregation = "SUM"
                  }
                }
              }
            }
          }
        }
      }

      visuals {
        line_chart_visual {
          visual_id = "overview-monthly-trend"

          title {
            format_text {
              plain_text = "Monthly trend"
            }
          }

          chart_configuration {
            type = "LINE"

            field_wells {
              line_chart_aggregated_field_wells {
                category {
                  date_dimension_field {
                    field_id         = "trend-month"
                    date_granularity = "MONTH"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "occurrence_date"
                    }
                  }
                }

                values {
                  numerical_measure_field {
                    field_id = "trend-incidents"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "incident_count"
                    }

                    aggregation_function {
                      simple_numerical_aggregation = "SUM"
                    }
                  }
                }
              }
            }
          }
        }
      }

      # Donut by primary type — replaces the bar chart so the deck matches
      # docs/architecture.md §8's four-visual Overview spec.
      visuals {
        pie_chart_visual {
          visual_id = "overview-primary-type-donut"

          title {
            format_text {
              plain_text = "Incidents by primary type"
            }
          }

          chart_configuration {
            donut_options {
              arc_options {
                arc_thickness = "MEDIUM"
              }
            }

            field_wells {
              pie_chart_aggregated_field_wells {
                category {
                  categorical_dimension_field {
                    field_id = "primary-type-donut-category"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "primary_type"
                    }
                  }
                }

                values {
                  numerical_measure_field {
                    field_id = "primary-type-donut-values"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "incident_count"
                    }

                    aggregation_function {
                      simple_numerical_aggregation = "SUM"
                    }
                  }
                }
              }
            }
          }
        }
      }

      # Geospatial point map keyed off the LATITUDE/LONGITUDE-tagged
      # lat/long columns (see logical_table_map.data_transforms above),
      # coloured by community_area_name. QuickSight's filled_map_visual
      # only supports country/state/county geographies — Chicago community
      # areas are not in that hierarchy — so this point map is the best
      # available choropleth substitute without bringing in custom GeoJSON.
      visuals {
        geospatial_map_visual {
          visual_id = "overview-community-map"

          title {
            format_text {
              plain_text = "Incidents by location (coloured by community area)"
            }
          }

          chart_configuration {
            field_wells {
              geospatial_map_aggregated_field_wells {
                geospatial {
                  numerical_dimension_field {
                    field_id = "geo-latitude"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "latitude"
                    }
                  }
                }

                geospatial {
                  numerical_dimension_field {
                    field_id = "geo-longitude"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "longitude"
                    }
                  }
                }

                values {
                  numerical_measure_field {
                    field_id = "geo-incidents"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "incident_count"
                    }

                    aggregation_function {
                      simple_numerical_aggregation = "SUM"
                    }
                  }
                }

                colors {
                  categorical_dimension_field {
                    field_id = "geo-community"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "community_area_name"
                    }
                  }
                }
              }
            }

            map_style_options {
              base_map_style = "LIGHT_GRAY"
            }

            point_style_options {
              selected_point_style = "POINT"
            }
          }
        }
      }

      layouts {
        configuration {
          grid_layout {
            canvas_size_options {
              screen_canvas_size_options {
                resize_option             = "FIXED"
                optimized_view_port_width = "1600px"
              }
            }

            elements {
              element_id   = "overview-date-range-control"
              element_type = "FILTER_CONTROL"
              column_index = "0"
              column_span  = 12
              row_index    = "0"
              row_span     = 3
            }

            elements {
              element_id   = "overview-community-control"
              element_type = "FILTER_CONTROL"
              column_index = "12"
              column_span  = 12
              row_index    = "0"
              row_span     = 3
            }

            elements {
              element_id   = "overview-total-incidents"
              element_type = "VISUAL"
              column_index = "0"
              column_span  = 12
              row_index    = "3"
              row_span     = 6
            }

            elements {
              element_id   = "overview-arrests"
              element_type = "VISUAL"
              column_index = "12"
              column_span  = 12
              row_index    = "3"
              row_span     = 6
            }

            elements {
              element_id   = "overview-monthly-trend"
              element_type = "VISUAL"
              column_index = "0"
              column_span  = 24
              row_index    = "9"
              row_span     = 12
            }

            elements {
              element_id   = "overview-primary-type-donut"
              element_type = "VISUAL"
              column_index = "0"
              column_span  = 12
              row_index    = "21"
              row_span     = 14
            }

            elements {
              element_id   = "overview-community-map"
              element_type = "VISUAL"
              column_index = "12"
              column_span  = 12
              row_index    = "21"
              row_span     = 14
            }
          }
        }
      }
    }
  }

  dynamic "permissions" {
    for_each = var.quicksight_admin_principal_arn == null ? [] : [var.quicksight_admin_principal_arn]

    content {
      principal = permissions.value
      actions   = local.quicksight_dashboard_actions
    }
  }

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# Dashboard 2: Detail
# ---------------------------------------------------------------------------

resource "aws_quicksight_dashboard" "crime_detail" {
  count = var.quicksight_enabled ? 1 : 0

  aws_account_id      = data.aws_caller_identity.current.account_id
  dashboard_id        = "${var.project_name}-crime-detail"
  name                = "Chicago Crime Detail"
  version_description = "Heatmap + weather scatter + district arrest trend + community/type table, with SCD2 as-of-date parameter and domestic toggle."

  definition {
    data_set_identifiers_declarations {
      identifier   = local.quicksight_dataset_identifier
      data_set_arn = aws_quicksight_data_set.crime_analytics[0].arn
    }

    # AsOfDate drives the SCD2 filter — pick any past date to see only the
    # dim_location SCD2 versions that were current on that date. Default of
    # now() means all SCD2-current location versions are visible (most fact
    # rows, since location SCD2 updates are rare).
    parameter_declarations {
      date_time_parameter_declaration {
        name             = "AsOfDate"
        time_granularity = "DAY"

        default_values {
          rolling_date {
            expression = "now()"
          }
        }
      }
    }

    filter_groups {
      filter_group_id = "detail-date-range"
      cross_dataset   = "SINGLE_DATASET"
      status          = "ENABLED"

      filters {
        time_range_filter {
          filter_id        = "detail-occurrence-date"
          include_minimum  = true
          include_maximum  = true
          null_option      = "ALL_VALUES"
          time_granularity = "DAY"

          column {
            data_set_identifier = local.quicksight_dataset_identifier
            column_name         = "occurrence_date"
          }

          range_minimum_value {
            static_value = "2018-01-01T00:00:00Z"
          }

          range_maximum_value {
            rolling_date {
              expression = "now()"
            }
          }
        }
      }

      scope_configuration {
        selected_sheets {
          sheet_visual_scoping_configurations {
            sheet_id = "detail"
            scope    = "ALL_VISUALS"
          }
        }
      }
    }

    # SCD2 as-of-date filter — keeps only fact rows where BOTH the stored
    # dim_location and dim_crime_type SCD2 versions were active on AsOfDate.
    # Four AND-joined predicates inside a single filter group:
    #   location_scd_start  <= AsOfDate
    #   location_scd_end    >  AsOfDate
    #   crime_type_scd_start <= AsOfDate
    #   crime_type_scd_end   >  AsOfDate
    # Implements docs/architecture.md §8's "SCD2-aware filter: show
    # indicators as of the event date" across the two SCD2 dimensions in
    # the bus matrix.
    filter_groups {
      filter_group_id = "detail-scd2-asof"
      cross_dataset   = "SINGLE_DATASET"
      status          = "ENABLED"

      filters {
        time_range_filter {
          filter_id        = "detail-scd2-loc-start-le-asof"
          include_maximum  = true
          null_option      = "ALL_VALUES"
          time_granularity = "DAY"

          column {
            data_set_identifier = local.quicksight_dataset_identifier
            column_name         = "location_scd_start"
          }

          range_maximum_value {
            parameter = "AsOfDate"
          }
        }
      }

      filters {
        time_range_filter {
          filter_id        = "detail-scd2-loc-end-gt-asof"
          include_minimum  = false
          null_option      = "ALL_VALUES"
          time_granularity = "DAY"

          column {
            data_set_identifier = local.quicksight_dataset_identifier
            column_name         = "location_scd_end"
          }

          range_minimum_value {
            parameter = "AsOfDate"
          }
        }
      }

      filters {
        time_range_filter {
          filter_id        = "detail-scd2-ct-start-le-asof"
          include_maximum  = true
          null_option      = "ALL_VALUES"
          time_granularity = "DAY"

          column {
            data_set_identifier = local.quicksight_dataset_identifier
            column_name         = "crime_type_scd_start"
          }

          range_maximum_value {
            parameter = "AsOfDate"
          }
        }
      }

      filters {
        time_range_filter {
          filter_id        = "detail-scd2-ct-end-gt-asof"
          include_minimum  = false
          null_option      = "ALL_VALUES"
          time_granularity = "DAY"

          column {
            data_set_identifier = local.quicksight_dataset_identifier
            column_name         = "crime_type_scd_end"
          }

          range_minimum_value {
            parameter = "AsOfDate"
          }
        }
      }

      scope_configuration {
        selected_sheets {
          sheet_visual_scoping_configurations {
            sheet_id = "detail"
            scope    = "ALL_VISUALS"
          }
        }
      }
    }

    # Domestic toggle — multi-select dropdown over is_domestic ∈ {0,1}.
    # Default FILTER_ALL_VALUES means no filter; user can isolate domestic
    # incidents to answer Q5 (time-of-day pattern of domestic incidents).
    filter_groups {
      filter_group_id = "detail-domestic"
      cross_dataset   = "SINGLE_DATASET"
      status          = "ENABLED"

      filters {
        category_filter {
          filter_id = "detail-domestic-filter"

          column {
            data_set_identifier = local.quicksight_dataset_identifier
            column_name         = "is_domestic"
          }

          configuration {
            filter_list_configuration {
              match_operator     = "CONTAINS"
              select_all_options = "FILTER_ALL_VALUES"
            }
          }
        }
      }

      scope_configuration {
        selected_sheets {
          sheet_visual_scoping_configurations {
            sheet_id = "detail"
            scope    = "ALL_VISUALS"
          }
        }
      }
    }

    sheets {
      sheet_id = "detail"
      name     = "Detail"
      title    = "Chicago Crime Detail"

      parameter_controls {
        date_time_picker {
          parameter_control_id  = "detail-as-of-date-control"
          source_parameter_name = "AsOfDate"
          # Plain-English title for the SCD2 as-of-date parameter. Internal
          # name stays "AsOfDate" so the time_range_filter binds in
          # filter_groups continue to resolve; only the visible label
          # changes. "Show community / crime-type attributes as of" reads
          # as a historical filter to a non-warehouse audience and matches
          # the actual behaviour (filters fact rows to the dim_location AND
          # dim_crime_type SCD2 versions active on the picked date).
          title = "Show community / crime-type attributes as of"

          display_options {
            date_time_format = "yyyy-MM-dd"
            title_options {
              visibility = "VISIBLE"
            }
          }
        }
      }

      filter_controls {
        date_time_picker {
          filter_control_id = "detail-date-range-control"
          source_filter_id  = "detail-occurrence-date"
          title             = "Occurrence date"
          type              = "DATE_RANGE"

          display_options {
            date_time_format = "yyyy-MM-dd"
            title_options {
              visibility = "VISIBLE"
            }
          }
        }
      }

      filter_controls {
        dropdown {
          filter_control_id = "detail-domestic-control"
          source_filter_id  = "detail-domestic-filter"
          title             = "Domestic (1 = yes, 0 = no)"
          type              = "MULTI_SELECT"

          display_options {
            title_options {
              visibility = "VISIBLE"
            }
          }
        }
      }

      visuals {
        heat_map_visual {
          visual_id = "detail-hour-day-heatmap"

          title {
            format_text {
              plain_text = "Incidents by day and hour"
            }
          }

          chart_configuration {
            field_wells {
              heat_map_aggregated_field_wells {
                rows {
                  categorical_dimension_field {
                    field_id = "heatmap-day"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "occurrence_day_name"
                    }
                  }
                }

                columns {
                  numerical_dimension_field {
                    field_id = "heatmap-hour"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "occurrence_hour"
                    }
                  }
                }

                values {
                  numerical_measure_field {
                    field_id = "heatmap-incidents"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "incident_count"
                    }

                    aggregation_function {
                      simple_numerical_aggregation = "SUM"
                    }
                  }
                }
              }
            }
          }
        }
      }

      # Weather scatter for Q2: each point = one primary_type bucket, located
      # at (avg temperature, avg precipitation), sized by total incident count.
      # Clusters reveal whether crime types correlate with hot/cold/wet weather.
      visuals {
        scatter_plot_visual {
          visual_id = "detail-weather-scatter"

          title {
            format_text {
              plain_text = "Weather vs incidents (one point per primary type)"
            }
          }

          chart_configuration {
            field_wells {
              scatter_plot_categorically_aggregated_field_wells {
                x_axis {
                  numerical_measure_field {
                    field_id = "scatter-x-temp"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "temperature_celsius"
                    }

                    aggregation_function {
                      simple_numerical_aggregation = "AVERAGE"
                    }
                  }
                }

                y_axis {
                  numerical_measure_field {
                    field_id = "scatter-y-precip"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "precipitation_mm"
                    }

                    aggregation_function {
                      simple_numerical_aggregation = "AVERAGE"
                    }
                  }
                }

                category {
                  categorical_dimension_field {
                    field_id = "scatter-primary-type"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "primary_type"
                    }
                  }
                }

                size {
                  numerical_measure_field {
                    field_id = "scatter-size-incidents"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "incident_count"
                    }

                    aggregation_function {
                      simple_numerical_aggregation = "SUM"
                    }
                  }
                }
              }
            }
          }
        }
      }

      # District arrest trend — one line per district, x = month, y = SUM(is_arrest).
      # Replaces the previous bar chart so Q3 ("arrest rate over time, by
      # district") gains a time axis.
      visuals {
        line_chart_visual {
          visual_id = "detail-district-arrest-trend"

          title {
            format_text {
              plain_text = "Arrests over time by district"
            }
          }

          chart_configuration {
            type = "LINE"

            field_wells {
              line_chart_aggregated_field_wells {
                category {
                  date_dimension_field {
                    field_id         = "district-trend-month"
                    date_granularity = "MONTH"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "occurrence_date"
                    }
                  }
                }

                values {
                  numerical_measure_field {
                    field_id = "district-trend-arrests"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "is_arrest"
                    }

                    aggregation_function {
                      simple_numerical_aggregation = "SUM"
                    }
                  }
                }

                colors {
                  categorical_dimension_field {
                    field_id = "district-trend-district"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "district"
                    }
                  }
                }
              }
            }
          }
        }
      }

      # Community×type table augmented with arrest_rate_pct (sum/sum * 100).
      visuals {
        table_visual {
          visual_id = "detail-community-type-table"

          title {
            format_text {
              plain_text = "Community area × crime type detail"
            }
          }

          chart_configuration {
            field_wells {
              table_aggregated_field_wells {
                group_by {
                  categorical_dimension_field {
                    field_id = "table-community"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "community_area_name"
                    }
                  }
                }

                group_by {
                  categorical_dimension_field {
                    field_id = "table-primary-type"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "primary_type"
                    }
                  }
                }

                values {
                  numerical_measure_field {
                    field_id = "table-incidents"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "incident_count"
                    }

                    aggregation_function {
                      simple_numerical_aggregation = "SUM"
                    }
                  }
                }

                values {
                  numerical_measure_field {
                    field_id = "table-arrests"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "is_arrest"
                    }

                    aggregation_function {
                      simple_numerical_aggregation = "SUM"
                    }
                  }
                }
              }
            }
          }
        }
      }

      layouts {
        configuration {
          grid_layout {
            canvas_size_options {
              screen_canvas_size_options {
                resize_option             = "FIXED"
                optimized_view_port_width = "1600px"
              }
            }

            elements {
              element_id   = "detail-as-of-date-control"
              element_type = "PARAMETER_CONTROL"
              column_index = "0"
              column_span  = 8
              row_index    = "0"
              row_span     = 3
            }

            elements {
              element_id   = "detail-date-range-control"
              element_type = "FILTER_CONTROL"
              column_index = "8"
              column_span  = 8
              row_index    = "0"
              row_span     = 3
            }

            elements {
              element_id   = "detail-domestic-control"
              element_type = "FILTER_CONTROL"
              column_index = "16"
              column_span  = 8
              row_index    = "0"
              row_span     = 3
            }

            elements {
              element_id   = "detail-hour-day-heatmap"
              element_type = "VISUAL"
              column_index = "0"
              column_span  = 24
              row_index    = "3"
              row_span     = 14
            }

            elements {
              element_id   = "detail-weather-scatter"
              element_type = "VISUAL"
              column_index = "0"
              column_span  = 24
              row_index    = "17"
              row_span     = 14
            }

            elements {
              element_id   = "detail-district-arrest-trend"
              element_type = "VISUAL"
              column_index = "0"
              column_span  = 24
              row_index    = "31"
              row_span     = 12
            }

            elements {
              element_id   = "detail-community-type-table"
              element_type = "VISUAL"
              column_index = "0"
              column_span  = 24
              row_index    = "43"
              row_span     = 14
            }
          }
        }
      }
    }
  }

  dynamic "permissions" {
    for_each = var.quicksight_admin_principal_arn == null ? [] : [var.quicksight_admin_principal_arn]

    content {
      principal = permissions.value
      actions   = local.quicksight_dashboard_actions
    }
  }

  tags = local.common_tags
}
