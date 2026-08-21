variable "bucket_name" {
  description = "Full bucket name, already composed by the caller; must be globally unique"
  type        = string
}

variable "state_key" {
  description = "Object key the Lambda reads and writes; the only key in this bucket"
  type        = string
  default     = "state.db"
}

variable "versioning_enabled" {
  description = "Whether object versioning is enabled; the only undo for a bad state.db write"
  type        = bool
  default     = true
}

variable "noncurrent_version_expiration_days" {
  description = "Days a superseded state.db version is retained before deletion"
  type        = number
  default     = 7
}

variable "tags" {
  description = "Tags applied to the bucket"
  type        = map(string)
  default     = {}
}
