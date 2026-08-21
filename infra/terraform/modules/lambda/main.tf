terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

locals {
  # Build a stable log-stream ARN across provider versions.
  log_group_arn = "arn:aws:logs:${var.region}:${var.account_id}:log-group:${var.log_group_name}:*"
}

data "aws_iam_policy_document" "trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = var.role_name
  assume_role_policy = data.aws_iam_policy_document.trust.json
  tags               = var.tags
}

# Limit log access to this function's log group.
data "aws_iam_policy_document" "logs" {
  statement {
    sid       = "WriteOwnLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = [local.log_group_arn]
  }
}

resource "aws_iam_role_policy" "logs" {
  name   = "${var.function_name}-logs"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.logs.json
}

# Allow reads and writes only for state.db.
data "aws_iam_policy_document" "state" {
  statement {
    sid       = "ReadWriteStateDb"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = [var.state_object_arn]
  }
}

resource "aws_iam_role_policy" "state" {
  name   = "${var.function_name}-state"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.state.json
}

# Create the log group first so its retention setting always applies.
resource "aws_cloudwatch_log_group" "this" {
  name              = var.log_group_name
  retention_in_days = var.log_retention_in_days
  tags              = var.tags
}

resource "aws_lambda_function" "this" {
  function_name = var.function_name
  role          = aws_iam_role.lambda.arn
  handler       = var.handler
  runtime       = var.runtime

  filename = var.package_path

  # Redeploy when the zip contents change.
  source_code_hash = filebase64sha256(var.package_path)

  # Allow enough time to fetch article pages.
  timeout     = var.timeout
  memory_size = var.memory_size

  environment {
    variables = {
      S3_BUCKET   = var.state_bucket_name
      NTFY_TOPIC  = var.ntfy_topic
      NTFY_SERVER = var.ntfy_server
    }
  }

  tags = var.tags

  depends_on = [aws_cloudwatch_log_group.this]
}
