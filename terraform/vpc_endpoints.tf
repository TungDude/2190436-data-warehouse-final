# ---------------------------------------------------------------------------
# VPC endpoints for in-VPC workloads to reach AWS APIs
#
# The DDL bootstrap Lambda and the silver->gold Glue jobs both run with
# `vpc_config` attached to default-VPC subnets so they can reach the
# private RDS instance. Default-VPC subnets are technically "public" (they
# carry an IGW default route), but VPC-attached Lambda / Glue ENIs do NOT
# receive public IPs, so the IGW route is unreachable from those ENIs.
#
# Three endpoints close the gap so the workloads can talk to AWS APIs
# without a NAT gateway:
#   - S3              (Gateway endpoint, free)              — Glue reads silver Parquet, libs.zip, script.py; Lambda reads SQL DDL
#   - Secrets Manager (Interface endpoint, ~$7.30/mo)        — Both fetch RDS creds
#   - CloudWatch Logs (Interface endpoint, ~$7.30/mo)        — Lambda writes logs; Glue writes via service-managed path so this is for Lambda primarily
#
# All three are wired to the default VPC. The Interface endpoints share a
# dedicated SG (`vpce`) that accepts HTTPS from the `glue_jdbc` SG only.
# ---------------------------------------------------------------------------

data "aws_route_tables" "default" {
  vpc_id = data.aws_vpc.default.id
}

resource "aws_security_group" "vpce" {
  name        = "${var.project_name}-vpce"
  description = "Shared security group for Interface VPC endpoints - accepts HTTPS from in-VPC Glue and Lambda workloads."
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "HTTPS from in-VPC Glue / Lambda workloads"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.glue_jdbc.id]
  }

  # No egress rules — endpoint ENIs are responders, not callers.

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# S3 Gateway endpoint — routed via prefix list, no SG / ENI required, no cost
# ---------------------------------------------------------------------------

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = data.aws_vpc.default.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = data.aws_route_tables.default.ids

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-vpce-s3"
  })
}

# ---------------------------------------------------------------------------
# Secrets Manager Interface endpoint — gives both Lambda and Glue a path to
# fetch RDS credentials without traversing the public internet
# ---------------------------------------------------------------------------

resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id              = data.aws_vpc.default.id
  service_name        = "com.amazonaws.${var.aws_region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = data.aws_subnets.default.ids
  security_group_ids  = [aws_security_group.vpce.id]
  private_dns_enabled = true

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-vpce-secretsmanager"
  })
}

# ---------------------------------------------------------------------------
# CloudWatch Logs Interface endpoint — VPC-attached Lambda writes its logs
# via this path (Glue uses the service-managed network for its own logs)
# ---------------------------------------------------------------------------

resource "aws_vpc_endpoint" "logs" {
  vpc_id              = data.aws_vpc.default.id
  service_name        = "com.amazonaws.${var.aws_region}.logs"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = data.aws_subnets.default.ids
  security_group_ids  = [aws_security_group.vpce.id]
  private_dns_enabled = true

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-vpce-logs"
  })
}

# ---------------------------------------------------------------------------
# STS Interface endpoint — Glue/Spark calls sts:AssumeRole and
# GetCallerIdentity during Hive metastore credential refresh. Without
# this endpoint the job dies at session start with "Connect to
# sts.<region>.amazonaws.com timed out" because the VPC has no NAT.
# ---------------------------------------------------------------------------

resource "aws_vpc_endpoint" "sts" {
  vpc_id              = data.aws_vpc.default.id
  service_name        = "com.amazonaws.${var.aws_region}.sts"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = data.aws_subnets.default.ids
  security_group_ids  = [aws_security_group.vpce.id]
  private_dns_enabled = true

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-vpce-sts"
  })
}

# ---------------------------------------------------------------------------
# Glue Interface endpoint — Glue jobs call back into the Glue Catalog API
# to enumerate silver tables before reading them. Same NAT-less reason as
# STS / Logs.
# ---------------------------------------------------------------------------

resource "aws_vpc_endpoint" "glue" {
  vpc_id              = data.aws_vpc.default.id
  service_name        = "com.amazonaws.${var.aws_region}.glue"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = data.aws_subnets.default.ids
  security_group_ids  = [aws_security_group.vpce.id]
  private_dns_enabled = true

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-vpce-glue"
  })
}
