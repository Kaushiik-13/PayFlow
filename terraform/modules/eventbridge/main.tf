resource "aws_iam_role" "glue_trigger_role" {
  name = "${var.project_name}-glue-trigger-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "glue_trigger_basic" {
  role       = aws_iam_role.glue_trigger_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "glue_trigger_glue" {
  name = "${var.project_name}-glue-trigger-glue-policy"
  role = aws_iam_role.glue_trigger_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["glue:StartJobRun"]
        Resource = "arn:aws:glue:${var.aws_region}:${var.account_id}:job/${var.project_name}-etl-job"
      },
      {
        Effect = "Allow"
        Action = ["glue:StartCrawler"]
        Resource = [
          "arn:aws:glue:${var.aws_region}:${var.account_id}:crawler/${var.project_name}-clean-crawler",
          "arn:aws:glue:${var.aws_region}:${var.account_id}:crawler/${var.project_name}-scored-crawler"
        ]
      }
    ]
  })
}

data "archive_file" "glue_trigger_lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/glue_trigger_lambda.zip"
  source {
    content  = <<-EOT
import json
import boto3

glue = boto3.client('glue')
JOB_NAME = '${var.project_name}-etl-job'

def lambda_handler(event, context):
    print(f"EventBridge event: {json.dumps(event)}")
    try:
        response = glue.start_job_run(JobName=JOB_NAME)
        print(f"Started Glue job run: {response['JobRunId']}")
        return {'statusCode': 200, 'body': json.dumps({'JobRunId': response['JobRunId']})}
    except Exception as e:
        print(f"Error starting Glue job: {e}")
        raise e
EOT
    filename = "lambda_function.py"
  }
}

data "archive_file" "crawler_trigger_lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/crawler_trigger_lambda.zip"
  source {
    content  = <<-EOT
import json
import boto3

glue = boto3.client('glue')
CLEAN_CRAWLER = '${var.project_name}-clean-crawler'
SCORED_CRAWLER = '${var.project_name}-scored-crawler'

def lambda_handler(event, context):
    print(f"EventBridge event: {json.dumps(event)}")
    for crawler_name in [CLEAN_CRAWLER, SCORED_CRAWLER]:
        try:
            glue.start_crawler(Name=crawler_name)
            print(f"Started crawler: {crawler_name}")
        except glue.exceptions.AlreadyRunningException:
            print(f"Crawler already running: {crawler_name}")
        except Exception as e:
            print(f"Error starting crawler {crawler_name}: {e}")
    return {'statusCode': 200, 'body': json.dumps({'message': 'Crawlers started'})}
EOT
    filename = "lambda_function.py"
  }
}

resource "aws_lambda_function" "glue_trigger" {
  function_name    = "${var.project_name}-glue-trigger"
  role             = aws_iam_role.glue_trigger_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.glue_trigger_lambda_zip.output_path
  source_code_hash = data.archive_file.glue_trigger_lambda_zip.output_base64sha256
  timeout          = 30
  memory_size      = 128
}

resource "aws_lambda_function" "crawler_trigger" {
  function_name    = "${var.project_name}-crawler-trigger"
  role             = aws_iam_role.glue_trigger_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.crawler_trigger_lambda_zip.output_path
  source_code_hash = data.archive_file.crawler_trigger_lambda_zip.output_base64sha256
  timeout          = 30
  memory_size      = 128
}

resource "aws_lambda_permission" "allow_eventbridge_s3_upload" {
  statement_id  = "AllowEventBridgeInvokeGlueTrigger"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.glue_trigger.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.s3_upload_trigger.arn
}

resource "aws_lambda_permission" "allow_eventbridge_glue_success" {
  statement_id  = "AllowEventBridgeInvokeCrawlerTrigger"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.crawler_trigger.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.glue_success_trigger.arn
}

resource "aws_cloudwatch_event_rule" "s3_upload_trigger" {
  name        = "${var.project_name}-s3-upload-trigger"
  description = "Trigger Glue ETL when raw data is uploaded to S3"
  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = { name = [var.raw_bucket] }
    }
  })
}

resource "aws_cloudwatch_event_target" "start_glue_job" {
  rule      = aws_cloudwatch_event_rule.s3_upload_trigger.name
  target_id = "TriggerGlueETLJob"
  arn       = aws_lambda_function.glue_trigger.arn
}

resource "aws_cloudwatch_event_rule" "glue_success_trigger" {
  name        = "${var.project_name}-glue-success-trigger"
  description = "Trigger Crawlers when Glue ETL job succeeds"
  event_pattern = jsonencode({
    source      = ["aws.glue"]
    detail-type = ["Glue Job Run Status"]
    detail = {
      jobName = ["${var.project_name}-etl-job"]
      state   = ["SUCCEEDED"]
    }
  })
}

resource "aws_cloudwatch_event_target" "start_crawlers" {
  rule      = aws_cloudwatch_event_rule.glue_success_trigger.name
  target_id = "TriggerCrawlers"
  arn       = aws_lambda_function.crawler_trigger.arn
}