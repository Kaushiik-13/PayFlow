terraform {
  backend "s3" {
    bucket         = "payflow-tfstate-104573823385"
    key            = "state/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "payflow-terraform-lock"
    encrypt        = true
  }
}

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}