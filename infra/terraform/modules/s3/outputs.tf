output "bucket_name" {
  description = "Name of the state bucket"
  value       = aws_s3_bucket.state.bucket
}

output "bucket_arn" {
  description = "ARN of the state bucket"
  value       = aws_s3_bucket.state.arn
}

output "state_object_arn" {
  description = "ARN of the single object the Lambda is granted access to"
  value       = "${aws_s3_bucket.state.arn}/${var.state_key}"
}

output "state_key" {
  description = "Object key holding the picker database"
  value       = var.state_key
}
