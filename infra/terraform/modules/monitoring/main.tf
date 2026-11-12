terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

# Alarms publish here; SNS emails the subscriber.
resource "aws_sns_topic" "alarms" {
  name = "${var.name_prefix}-alarms"
  tags = var.tags
}

# Stays "pending confirmation" until the link in AWS's first email is clicked.
resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

locals {
  dimensions = { FunctionName = var.function_name }
}

# A scheduled job that stops running emits no datapoints at all, so missing
# data has to count as breaching. Hourly periods with 26 of 26 breaching means
# "no invocation for 26 hours": a daily 07:00 run has 2 hours of slack for
# retries and metric lag before a false alarm.
resource "aws_cloudwatch_metric_alarm" "missed_run" {
  alarm_name          = "${var.name_prefix}-missed-run"
  alarm_description   = "The picker has not run for ${var.missed_run_hours} hours."
  namespace           = "AWS/Lambda"
  metric_name         = "Invocations"
  dimensions          = local.dimensions
  statistic           = "Sum"
  period              = 3600
  evaluation_periods  = var.missed_run_hours
  datapoints_to_alarm = var.missed_run_hours
  comparison_operator = "LessThanThreshold"
  threshold           = 1
  treat_missing_data  = "breaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  tags                = var.tags
}

# Any uncaught exception, timeout, or out-of-memory kill.
resource "aws_cloudwatch_metric_alarm" "errors" {
  alarm_name          = "${var.name_prefix}-errors"
  alarm_description   = "The picker failed. Check the log group for the traceback."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = local.dimensions
  statistic           = "Sum"
  period              = 3600
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  tags                = var.tags
}

# Early warning before the errors alarm: the page-fetch cap keeps the run
# inside the timeout, and this says when that margin is getting thin.
resource "aws_cloudwatch_metric_alarm" "slow_run" {
  alarm_name          = "${var.name_prefix}-slow-run"
  alarm_description   = "A run used more than 80% of the ${var.function_timeout_seconds}s timeout."
  namespace           = "AWS/Lambda"
  metric_name         = "Duration"
  dimensions          = local.dimensions
  statistic           = "Maximum"
  period              = 3600
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.function_timeout_seconds * 1000 * 0.8
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  tags                = var.tags
}

resource "aws_cloudwatch_dashboard" "this" {
  dashboard_name = var.name_prefix

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "alarm"
        x      = 0
        y      = 0
        width  = 24
        height = 3
        properties = {
          title = "Alarms"
          alarms = [
            aws_cloudwatch_metric_alarm.missed_run.arn,
            aws_cloudwatch_metric_alarm.errors.arn,
            aws_cloudwatch_metric_alarm.slow_run.arn,
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 3
        width  = 12
        height = 6
        properties = {
          title  = "Runs and errors (daily)"
          region = var.region
          view   = "timeSeries"
          stat   = "Sum"
          period = 86400
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", var.function_name],
            ["AWS/Lambda", "Errors", "FunctionName", var.function_name],
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 3
        width  = 12
        height = 6
        properties = {
          title  = "Run duration (ms)"
          region = var.region
          view   = "timeSeries"
          period = 3600
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", var.function_name, { stat = "Maximum" }],
          ]
          annotations = {
            horizontal = [
              { label = "timeout", value = var.function_timeout_seconds * 1000 },
            ]
          }
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 9
        width  = 12
        height = 6
        properties = {
          title  = "Scheduler invocation attempts (daily)"
          region = var.region
          view   = "timeSeries"
          stat   = "Sum"
          period = 86400
          metrics = [
            ["AWS/Scheduler", "InvocationAttemptCount", "ScheduleGroup", var.schedule_group_name],
          ]
        }
      },
      {
        type   = "log"
        x      = 12
        y      = 9
        width  = 12
        height = 6
        properties = {
          title  = "Recent errors"
          region = var.region
          view   = "table"
          query  = "SOURCE '/aws/lambda/${var.function_name}' | fields @timestamp, @message | filter @message like /(?i)(error|exception|traceback)/ | sort @timestamp desc | limit 20"
        }
      },
    ]
  })
}
