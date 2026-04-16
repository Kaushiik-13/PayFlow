resource "aws_lakeformation_data_lake_settings" "settings" {
  admins = [var.admin_role_arn]
}

resource "aws_lakeformation_resource" "clean_bucket" {
  arn = "arn:aws:s3:::${var.clean_bucket}"
}

resource "aws_lakeformation_resource" "scored_bucket" {
  arn = "arn:aws:s3:::${var.scored_bucket}"
}

resource "aws_lakeformation_permissions" "admin_database" {
  principal   = var.admin_role_arn
  permissions = ["ALL"]

  database {
    name = "payflow_db"
  }
}

resource "aws_lakeformation_permissions" "analyst_database" {
  principal   = var.analyst_role_arn
  permissions = ["DESCRIBE"]

  database {
    name = "payflow_db"
  }
}