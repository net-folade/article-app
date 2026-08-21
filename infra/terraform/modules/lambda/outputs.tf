output "function_name" {
  description = "Name of the picker function"
  value       = aws_lambda_function.this.function_name
}

output "function_arn" {
  description = "ARN of the picker function"
  value       = aws_lambda_function.this.arn
}

output "role_name" {
  description = "Name of the execution role, for the IAM audit commands in SECURITY.md"
  value       = aws_iam_role.lambda.name
}

output "role_arn" {
  description = "ARN of the execution role"
  value       = aws_iam_role.lambda.arn
}

output "log_group_name" {
  description = "Where the function writes its logs"
  value       = aws_cloudwatch_log_group.this.name
}
