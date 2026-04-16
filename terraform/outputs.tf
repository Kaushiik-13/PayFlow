output "raw_bucket" {
  value       = module.s3.raw_bucket
  description = "S3 bucket for raw transaction data"
}

output "clean_bucket" {
  value       = module.s3.clean_bucket
  description = "S3 bucket for clean Parquet data"
}

output "scored_bucket" {
  value       = module.s3.scored_bucket
  description = "S3 bucket for scored anomaly data"
}

output "athena_results_bucket" {
  value       = module.s3.athena_results_bucket
  description = "S3 bucket for Athena query results"
}

output "scripts_bucket" {
  value       = module.s3.scripts_bucket
  description = "S3 bucket for Glue scripts"
}

output "glue_role_arn" {
  value       = module.iam.glue_role_arn
  description = "ARN of the Glue service role"
}

output "lambda_role_arn" {
  value       = module.iam.lambda_role_arn
  description = "ARN of the Lambda execution role"
}

output "lambda_arn" {
  value       = module.lambda.lambda_arn
  description = "ARN of the Lambda anomaly detector function"
}

output "sns_topic_arn" {
  value       = module.lambda.sns_topic_arn
  description = "ARN of the SNS fraud alert topic"
}

output "eventbridge_role_arn" {
  value       = module.iam.eventbridge_role_arn
  description = "ARN of the EventBridge invocation role"
}