terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

# A dedicated group so the trust policy below scopes to this project alone.
resource "aws_scheduler_schedule_group" "this" {
  name = var.schedule_group
  tags = var.tags
}

# Allow only this account, and only schedules in our group, to assume the role.
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
      values   = [aws_scheduler_schedule_group.this.arn]
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
  group_name = aws_scheduler_schedule_group.this.name

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
