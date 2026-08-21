data "aws_caller_identity" "current" {}

locals {
  # Include the environment in every shared AWS resource name.
  name_prefix = "${var.project}-${var.environment}"

  # Define full resource names here.
  bucket_name         = "${local.name_prefix}-state-${var.bucket_suffix}"
  function_name       = "${local.name_prefix}-picker"
  function_role_name  = "${local.name_prefix}-picker-role"
  log_group_name      = "/aws/lambda/${local.name_prefix}-picker"
  schedule_name       = "${local.name_prefix}-daily"
  schedule_group_name = local.name_prefix
  scheduler_role_name = "${local.name_prefix}-scheduler-role"

  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# This bucket stores state but does not invoke Lambda.
module "s3" {
  source = "../../modules/s3"

  bucket_name                        = local.bucket_name
  noncurrent_version_expiration_days = var.noncurrent_version_expiration_days
  tags                               = local.tags
}

module "lambda" {
  source = "../../modules/lambda"

  function_name  = local.function_name
  role_name      = local.function_role_name
  log_group_name = local.log_group_name

  region     = var.region
  account_id = data.aws_caller_identity.current.account_id

  state_bucket_name = module.s3.bucket_name
  state_object_arn  = module.s3.state_object_arn

  ntfy_topic  = var.ntfy_topic
  ntfy_server = var.ntfy_server

  # `make package` writes the zip at this path.
  package_path = "${path.root}/../../../../build/deploy.zip"

  timeout               = var.lambda_timeout
  memory_size           = var.lambda_memory_size
  log_retention_in_days = var.log_retention_in_days
  tags                  = local.tags
}

module "scheduler" {
  source = "../../modules/scheduler"

  schedule_name  = local.schedule_name
  role_name      = local.scheduler_role_name
  schedule_group = local.schedule_group_name

  account_id = data.aws_caller_identity.current.account_id

  function_arn        = module.lambda.function_arn
  schedule_expression = var.schedule_expression
  schedule_state      = var.schedule_state
  tags                = local.tags
}
