resource "aws_athena_workgroup" "payflow" {
  name = "${var.project_name}-workgroup"

  configuration {
    result_configuration {
      output_location = "s3://${var.athena_results_bucket}/"
    }
    bytes_scanned_cutoff_per_query = 1073741824
  }
}