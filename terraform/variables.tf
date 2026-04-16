variable "aws_region" {
  description = "AWS region for all resources"
  default     = "ap-south-1"
  type        = string
}

variable "env" {
  description = "Environment name (dev, staging, prod)"
  default     = "dev"
  type        = string
}

variable "project_name" {
  description = "Project name used as prefix for all resources"
  default     = "payflow"
  type        = string
}

variable "alert_email" {
  description = "Email address for SNS fraud alerts"
  default     = "kaushiik.23cs@kct.ac.in"
  type        = string
}

variable "account_id" {
  description = "AWS Account ID for bucket name uniqueness"
  default     = "104573823385"
  type        = string
}