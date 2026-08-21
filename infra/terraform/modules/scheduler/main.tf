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
  # Build the ARN here to avoid a dependency cycle with the role.
  schedule_arn = "arn:aws:scheduler:${var.region}:${var.account_id}:schedule/${var.schedule_group}/${var.schedule_name}"
}

# Allow only this account and schedule to assume the role.
data "aws_iam_policy_document" "trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [var.account_id]
    }

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [local.schedule_arn]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = var.role_name
  assume_role_policy = data.aws_iam_policy_document.trust.json
  tags               = var.tags
}

# Allow the scheduler role to invoke only this function.
data "aws_iam_policy_document" "invoke" {
  statement {
    sid       = "InvokePickerFunction"
    effect    = "Allow"
    actions   = ["lambda:InvokeFunction"]
    resources = [var.function_arn]
  }
}

resource "aws_iam_role_policy" "invoke" {
  name   = "${var.schedule_name}-invoke"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.invoke.json
}

resource "aws_scheduler_schedule" "this" {
  name       = var.schedule_name
  group_name = var.schedule_group

  # Development stays disabled until invoked manually.
  state = var.schedule_state

  schedule_expression          = var.schedule_expression
  schedule_expression_timezone = var.schedule_timezone

  # Run at the exact cron time.
  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = var.function_arn
    role_arn = aws_iam_role.scheduler.arn

    retry_policy {
      maximum_retry_attempts = var.maximum_retry_attempts
    }
  }
}
