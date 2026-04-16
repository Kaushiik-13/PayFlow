resource "aws_sns_topic" "fraud_alerts" {
  name = "${var.project_name}-fraud-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.fraud_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_lambda_function" "anomaly_detector" {
  function_name = "${var.project_name}-anomaly-detector"
  role          = var.lambda_role_arn
  package_type  = "Image"
  image_uri     = "${var.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.project_name}-anomaly-detector:latest"
  timeout       = 900
  memory_size   = 3008

  environment {
    variables = {
      CLEAN_BUCKET  = var.clean_bucket
      SCORED_BUCKET = var.scored_bucket
      SNS_TOPIC_ARN = aws_sns_topic.fraud_alerts.arn
      REGION        = var.aws_region
    }
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.lambda_dlq.arn
  }
}

resource "aws_iam_role_policy" "lambda_sns" {
  name = "${var.project_name}-lambda-sns-publish"
  role = var.lambda_role_name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = aws_sns_topic.fraud_alerts.arn
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.lambda_dlq.arn
      }
    ]
  })
}

resource "aws_sqs_queue" "lambda_dlq" {
  name                      = "${var.project_name}-lambda-dlq"
  message_retention_seconds = 1209600
}

resource "aws_sqs_queue_policy" "lambda_dlq_policy" {
  queue_url = aws_sqs_queue.lambda_dlq.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.lambda_dlq.arn
      Condition = {
        ArnEquals = {
          "aws:SourceArn" = aws_lambda_function.anomaly_detector.arn
        }
      }
    }]
  })
}

output "sns_topic_arn" { value = aws_sns_topic.fraud_alerts.arn }
output "lambda_arn" { value = aws_lambda_function.anomaly_detector.arn }