variable "name_prefix" {
  description = "Prefix for the topic, alarms and dashboard, e.g. article-app-prod"
  type        = string
}

variable "region" {
  description = "Region the dashboard widgets read metrics from"
  type        = string
}

variable "function_name" {
  description = "Picker function the alarms watch"
  type        = string
}

variable "function_timeout_seconds" {
  description = "Function timeout; the slow-run alarm fires at 80% of it"
  type        = number
}

variable "schedule_group_name" {
  description = "Scheduler group whose invocation attempts the dashboard shows"
  type        = string
}

variable "alarm_email" {
  description = "Address the alarm emails go to; it must confirm the SNS subscription once"
  type        = string
  sensitive   = true
}

variable "missed_run_hours" {
  description = "Hours without an invocation before the missed-run alarm fires"
  type        = number
  default     = 26
}

variable "tags" {
  description = "Tags applied to every resource"
  type        = map(string)
  default     = {}
}
