variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Project name; first segment of every resource name"
  type        = string
  default     = "article-app"
}

variable "environment" {
  description = "Environment name; second segment of every resource name"
  type        = string
}

variable "bucket_suffix" {
  description = "Random suffix that makes the state bucket name globally unique"
  type        = string
}

variable "ntfy_topic" {
  description = "ntfy topic this environment pushes to; dev must differ from prod"
  type        = string
  sensitive   = true
}

variable "ntfy_server" {
  description = "ntfy server base URL"
  type        = string
  default     = "https://ntfy.sh"
}

variable "schedule_expression" {
  description = "Cron expression for the daily run, evaluated in UTC"
  type        = string
  default     = "cron(0 7 * * ? *)"
}

variable "schedule_state" {
  description = "ENABLED or DISABLED"
  type        = string
}

variable "lambda_timeout" {
  description = "Function timeout in seconds"
  type        = number
  default     = 300
}

variable "lambda_memory_size" {
  description = "Function memory in MB"
  type        = number
  default     = 512
}

variable "log_retention_in_days" {
  description = "CloudWatch log retention"
  type        = number
  default     = 7
}

variable "noncurrent_version_expiration_days" {
  description = "Days a superseded state.db version is kept"
  type        = number
  default     = 7
}
