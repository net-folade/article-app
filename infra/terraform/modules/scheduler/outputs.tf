output "schedule_name" {
  description = "Name of the daily schedule"
  value       = aws_scheduler_schedule.this.name
}

output "schedule_arn" {
  description = "ARN of the daily schedule"
  value       = aws_scheduler_schedule.this.arn
}

output "schedule_state" {
  description = "Whether the schedule fires on its own"
  value       = aws_scheduler_schedule.this.state
}

output "role_name" {
  description = "Name of the scheduler role, for the IAM audit commands in SECURITY.md"
  value       = aws_iam_role.scheduler.name
}
