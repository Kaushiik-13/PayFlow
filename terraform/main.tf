module "s3" {
  source       = "./modules/s3"
  project_name = var.project_name
  env          = var.env
  account_id   = var.account_id
}

module "iam" {
  source         = "./modules/iam"
  project_name   = var.project_name
  aws_region     = var.aws_region
  account_id     = var.account_id
  raw_bucket     = module.s3.raw_bucket
  clean_bucket   = module.s3.clean_bucket
  scored_bucket  = module.s3.scored_bucket
  scripts_bucket = module.s3.scripts_bucket
}

module "glue" {
  source         = "./modules/glue"
  project_name   = var.project_name
  glue_role_arn  = module.iam.glue_role_arn
  raw_bucket     = module.s3.raw_bucket
  clean_bucket   = module.s3.clean_bucket
  scored_bucket  = module.s3.scored_bucket
  scripts_bucket = module.s3.scripts_bucket
}

module "athena" {
  source                = "./modules/athena"
  project_name          = var.project_name
  athena_results_bucket = module.s3.athena_results_bucket
}

module "lambda" {
  source           = "./modules/lambda"
  project_name     = var.project_name
  aws_region       = var.aws_region
  account_id       = var.account_id
  lambda_role_arn  = module.iam.lambda_role_arn
  lambda_role_name = "${var.project_name}-lambda-role"
  clean_bucket     = module.s3.clean_bucket
  scored_bucket    = module.s3.scored_bucket
  alert_email      = var.alert_email
}

module "lake_formation" {
  source           = "./modules/lake_formation"
  admin_role_arn   = module.iam.glue_role_arn
  analyst_role_arn = module.iam.lambda_role_arn
  clean_bucket     = module.s3.clean_bucket
  scored_bucket    = module.s3.scored_bucket
}

module "eventbridge" {
  source       = "./modules/eventbridge"
  project_name = var.project_name
  aws_region   = var.aws_region
  account_id   = var.account_id
  raw_bucket   = module.s3.raw_bucket
}