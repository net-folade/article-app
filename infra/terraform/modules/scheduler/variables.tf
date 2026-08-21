variable "schedule_name" {
  description = "Full schedule name, already composed by the caller"
  type        = string
}

variable "role_name" {
  description = "Full scheduler role name, already composed by the caller"
  type        = string
}

variable "schedule_group" {
  description = "Dedicated scheduler group created by this module; its ARN is what aws:SourceArn pins"
  type        = string
}

variable "account_id" {
  description = "Account ID pinned by aws:SourceAccount in the trust policy"
  type        = string
}

variable "function_arn" {
  description = "ARN of the function this schedule may invoke, and nothing else"
  type        = string
}

variable "schedule_expression" {
  description = "Cron expression for the daily run"
  type        = string
  default     = "cron(0 7 * * ? *)"
}

variable "schedule_timezone" {
  description = "Timezone the cron expression is evaluated in"
  type        = string
  default     = "UTC"
}

variable "schedule_state" {
  description = "ENABLED or DISABLED; dev runs DISABLED so it fires only on demand"
  type        = string
  default     = "ENABLED"

  validation {
    condition     = contains(["ENABLED", "DISABLED"], var.schedule_state)
    error_message = "schedule_state must be ENABLED or DISABLED."
  }
}

variable "maximum_retry_attempts" {
  description = "Retries if the invocation itself fails; 0 keeps one article per day"
  type        = number
  default     = 0
}

variable "tags" {
  description = "Tags applied to the scheduler role"
  type        = map(string)
  default     = {}
}
