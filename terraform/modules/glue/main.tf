resource "aws_glue_catalog_database" "payflow_db" {
  name = "payflow_db"
}

resource "aws_glue_job" "etl_job" {
  name              = "${var.project_name}-etl-job"
  role_arn          = var.glue_role_arn
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 30

  command {
    script_location = "s3://${var.scripts_bucket}/glue_etl_job.py"
    python_version  = "3"
  }

  default_arguments = {
    "--RAW_BUCKET"          = var.raw_bucket
    "--CLEAN_BUCKET"        = var.clean_bucket
    "--job-language"        = "python"
    "--enable-auto-scaling" = "false"
    "--TempDir"             = "s3://${var.scripts_bucket}/temp/"
  }
}

resource "aws_glue_crawler" "clean_crawler" {
  name          = "${var.project_name}-clean-crawler"
  role          = var.glue_role_arn
  database_name = aws_glue_catalog_database.payflow_db.name

  s3_target {
    path = "s3://${var.clean_bucket}/"
  }

  schedule = ""
}

resource "aws_glue_crawler" "scored_crawler" {
  name          = "${var.project_name}-scored-crawler"
  role          = var.glue_role_arn
  database_name = aws_glue_catalog_database.payflow_db.name

  s3_target {
    path = "s3://${var.scored_bucket}/"
  }

  schedule = ""
}