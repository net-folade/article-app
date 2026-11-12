# These ARNs go into GitHub secrets, not the repo: they contain the account ID.
output "plan_role_arn" {
  description = "Repository secret AWS_PLAN_ROLE_ARN"
  value       = aws_iam_role.plan.arn
}

output "deploy_role_arns" {
  description = "Environment secret AWS_DEPLOY_ROLE_ARN in the dev and prod environments"
  value       = { for env, role in aws_iam_role.deploy : env => role.arn }
}
