variable "function_name" {
  description = "Full function name, already composed by the caller"
  type        = string
}

variable "role_name" {
  description = "Full execution role name, already composed by the caller"
  type        = string
}

variable "log_group_name" {
  description = "Full CloudWatch log group name, already composed by the caller"
  type        = string
}

variable "region" {
  description = "Region the log group ARN is composed against"
  type        = string
}

variable "account_id" {
  description = "Account ID the log group ARN is composed against"
  type        = string
}

variable "state_bucket_name" {
  description = "State bucket name, exposed to the handler as S3_BUCKET"
  type        = string
}

variable "state_object_arn" {
  description = "ARN of the single S3 object this function may read and write"
  type        = string
}

variable "ntfy_topic" {
  description = "ntfy topic the notification is pushed to; the only secret in the stack"
  type        = string
  sensitive   = true
}

variable "ntfy_server" {
  description = "ntfy server base URL"
  type        = string
  default     = "https://ntfy.sh"
}

variable "package_path" {
  description = "Path to the deployment zip built by scripts/package_lambda.sh"
  type        = string
}

variable "handler" {
  description = "Lambda handler entrypoint"
  type        = string
  default     = "src.handler.lambda_handler"
}

variable "runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "python3.13"
}

variable "timeout" {
  description = "Function timeout in seconds; the teaser-feed page fetch needs well over 60"
  type        = number
  default     = 300
}

variable "memory_size" {
  description = "Function memory in MB; also scales CPU, which the page fetch benefits from"
  type        = number
  default     = 512
}

variable "log_retention_in_days" {
  description = "CloudWatch log retention"
  type        = number
  default     = 7
}

variable "tags" {
  description = "Tags applied to the function, role, and log group"
  type        = map(string)
  default     = {}
}
