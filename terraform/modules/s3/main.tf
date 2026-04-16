resource "aws_s3_bucket" "raw" {
  bucket = "${var.project_name}-raw-transactions-${var.env}-${var.account_id}"
  tags   = { Project = var.project_name, Stage = "raw" }
}

resource "aws_s3_bucket" "clean" {
  bucket = "${var.project_name}-clean-transactions-${var.env}-${var.account_id}"
  tags   = { Project = var.project_name, Stage = "clean" }
}

resource "aws_s3_bucket" "scored" {
  bucket = "${var.project_name}-scored-transactions-${var.env}-${var.account_id}"
  tags   = { Project = var.project_name, Stage = "scored" }
}

resource "aws_s3_bucket" "athena_results" {
  bucket = "${var.project_name}-athena-results-${var.env}-${var.account_id}"
  tags   = { Project = var.project_name, Stage = "results" }
}

resource "aws_s3_bucket" "scripts" {
  bucket = "${var.project_name}-glue-scripts-${var.env}-${var.account_id}"
  tags   = { Project = var.project_name, Stage = "scripts" }
}

resource "aws_s3_bucket_versioning" "raw" {
  bucket = aws_s3_bucket.raw.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_versioning" "clean" {
  bucket = aws_s3_bucket.clean.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_versioning" "scored" {
  bucket = aws_s3_bucket.scored.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_versioning" "scripts" {
  bucket = aws_s3_bucket.scripts.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket                  = aws_s3_bucket.raw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "clean" {
  bucket                  = aws_s3_bucket.clean.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "scored" {
  bucket                  = aws_s3_bucket.scored.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_notification" "raw_eventbridge" {
  bucket = aws_s3_bucket.raw.id

  eventbridge = true
}

output "raw_bucket" { value = aws_s3_bucket.raw.id }
output "clean_bucket" { value = aws_s3_bucket.clean.id }
output "scored_bucket" { value = aws_s3_bucket.scored.id }
output "athena_results_bucket" { value = aws_s3_bucket.athena_results.id }
output "scripts_bucket" { value = aws_s3_bucket.scripts.id }