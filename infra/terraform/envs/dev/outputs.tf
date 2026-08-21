output "function_name" {
  description = "Picker function for this environment"
  value       = module.lambda.function_name
}

output "bucket_name" {
  description = "State bucket holding state.db"
  value       = module.s3.bucket_name
}

output "state_key" {
  description = "Object key holding the picker database"
  value       = module.s3.state_key
}

output "log_group_name" {
  description = "Where the function writes its logs"
  value       = module.lambda.log_group_name
}

output "schedule_name" {
  description = "Name of the daily schedule"
  value       = module.scheduler.schedule_name
}

output "schedule_state" {
  description = "Whether the schedule fires on its own"
  value       = module.scheduler.schedule_state
}

output "lambda_role_name" {
  description = "Execution role name, for the audit commands in SECURITY.md"
  value       = module.lambda.role_name
}

output "scheduler_role_name" {
  description = "Scheduler role name, for the audit commands in SECURITY.md"
  value       = module.scheduler.role_name
}
