output "dashboard_name" {
  description = "CloudWatch dashboard for this environment"
  value       = aws_cloudwatch_dashboard.this.dashboard_name
}

output "alarm_topic_arn" {
  description = "SNS topic the alarms publish to"
  value       = aws_sns_topic.alarms.arn
}
