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

  quicksight_crime_analytics_sql = <<-SQL
    SELECT
      fc.crime_id::bigint                         AS crime_id,
      fc.incident_count::integer                  AS incident_count,
      fc.is_arrest::integer                       AS is_arrest,
      fc.is_domestic::integer                     AS is_domestic,
      fc.hours_to_update::integer                 AS hours_to_update,
      fc.latitude::numeric                        AS latitude,
      fc.longitude::numeric                       AS longitude,
      fc.temperature_celsius::numeric             AS temperature_celsius,
      fc.precipitation_mm::numeric                AS precipitation_mm,
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
      COALESCE(ct.primary_type, 'Unknown')        AS primary_type,
      COALESCE(ct.description, 'Unknown')         AS crime_description,
      COALESCE(ct.fbi_code, 'Unknown')            AS fbi_code,
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
  SQL

  quicksight_crime_analytics_columns = [
    { name = "crime_id", type = "INTEGER" },
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
    { name = "primary_type", type = "STRING" },
    { name = "crime_description", type = "STRING" },
    { name = "fbi_code", type = "STRING" },
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

  quicksight_dashboard_actions = [
    "quicksight:DescribeDashboard",
    "quicksight:DescribeDashboardDefinition",
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

  tags = local.common_tags
}

resource "aws_quicksight_data_set" "crime_analytics" {
  count = var.quicksight_enabled ? 1 : 0

  aws_account_id = data.aws_caller_identity.current.account_id
  data_set_id    = "${var.project_name}-crime-analytics"
  name           = "${var.project_name} Crime Analytics"
  import_mode    = "SPICE"

  physical_table_map {
    physical_table_map_id = "crime_analytics_sql"

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

  dynamic "permissions" {
    for_each = var.quicksight_admin_principal_arn == null ? [] : [var.quicksight_admin_principal_arn]

    content {
      principal = permissions.value
      actions   = local.quicksight_data_set_actions
    }
  }

  data_set_usage_configuration {
    disable_use_as_direct_query_source = true
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
  version_description = "Initial Terraform-managed overview dashboard"

  definition {
    data_set_identifiers_declarations {
      identifier   = local.quicksight_dataset_identifier
      data_set_arn = aws_quicksight_data_set.crime_analytics[0].arn
    }

    sheets {
      sheet_id = "overview"
      name     = "Overview"
      title    = "Chicago Crime Overview"

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
          }
        }
      }

      visuals {
        kpi_visual {
          visual_id = "overview-total-arrests"

          title {
            format_text {
              plain_text = "Arrests"
            }
          }

          chart_configuration {
            field_wells {
              values {
                numerical_measure_field {
                  field_id = "total-arrests"

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

      visuals {
        bar_chart_visual {
          visual_id = "overview-primary-type"

          title {
            format_text {
              plain_text = "Incidents by primary type"
            }
          }

          chart_configuration {
            orientation      = "HORIZONTAL"
            bars_arrangement = "STACKED"

            field_wells {
              bar_chart_aggregated_field_wells {
                category {
                  categorical_dimension_field {
                    field_id = "primary-type"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "primary_type"
                    }
                  }
                }

                values {
                  numerical_measure_field {
                    field_id = "primary-type-incidents"

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
              element_id   = "overview-total-incidents"
              element_type = "VISUAL"
              column_index = "0"
              column_span  = 12
              row_index    = "0"
              row_span     = 6
            }

            elements {
              element_id   = "overview-total-arrests"
              element_type = "VISUAL"
              column_index = "12"
              column_span  = 12
              row_index    = "0"
              row_span     = 6
            }

            elements {
              element_id   = "overview-monthly-trend"
              element_type = "VISUAL"
              column_index = "0"
              column_span  = 24
              row_index    = "6"
              row_span     = 12
            }

            elements {
              element_id   = "overview-primary-type"
              element_type = "VISUAL"
              column_index = "0"
              column_span  = 24
              row_index    = "18"
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
  version_description = "Initial Terraform-managed detail dashboard"

  definition {
    data_set_identifiers_declarations {
      identifier   = local.quicksight_dataset_identifier
      data_set_arn = aws_quicksight_data_set.crime_analytics[0].arn
    }

    sheets {
      sheet_id = "detail"
      name     = "Detail"
      title    = "Chicago Crime Detail"

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

      visuals {
        bar_chart_visual {
          visual_id = "detail-district-arrests"

          title {
            format_text {
              plain_text = "Arrests by district"
            }
          }

          chart_configuration {
            orientation      = "VERTICAL"
            bars_arrangement = "STACKED"

            field_wells {
              bar_chart_aggregated_field_wells {
                category {
                  categorical_dimension_field {
                    field_id = "district"

                    column {
                      data_set_identifier = local.quicksight_dataset_identifier
                      column_name         = "district"
                    }
                  }
                }

                values {
                  numerical_measure_field {
                    field_id = "district-arrests"

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

      visuals {
        table_visual {
          visual_id = "detail-community-type-table"

          title {
            format_text {
              plain_text = "Community area and crime type detail"
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
              element_id   = "detail-hour-day-heatmap"
              element_type = "VISUAL"
              column_index = "0"
              column_span  = 24
              row_index    = "0"
              row_span     = 14
            }

            elements {
              element_id   = "detail-district-arrests"
              element_type = "VISUAL"
              column_index = "0"
              column_span  = 24
              row_index    = "14"
              row_span     = 12
            }

            elements {
              element_id   = "detail-community-type-table"
              element_type = "VISUAL"
              column_index = "0"
              column_span  = 24
              row_index    = "26"
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
