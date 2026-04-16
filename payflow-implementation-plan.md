# PayFlow — Payment Transaction Anomaly Detection Pipeline
### Implementation Plan | Cost-Optimized | ~$0.61 for 1 Week

> **By Kaushiik Arul** | Cloud & Data Engineering Project  
> Stack: AWS S3 · Glue · Lake Formation · Athena · Lambda · EventBridge · SNS · QuickSight · Terraform

---

## Project Summary

PayFlow is an end-to-end cloud-scale ETL pipeline that ingests raw payment transactions, processes and enriches them through AWS Glue, governs access via Lake Formation, and runs an **unsupervised Isolation Forest ML model on AWS Lambda Container Image** to automatically detect fraudulent anomalies — without needing labeled data. The pipeline is **orchestrated via EventBridge + Lambda intermediary functions**: S3 upload triggers a Glue trigger Lambda (which starts the Glue job), Glue completion triggers a Crawler trigger Lambda (which starts both crawlers), and Lambda is invoked manually after crawlers finish. Results are queried via Athena and visualized on **Amazon QuickSight** with real-time SNS alerts.

---

## Cost Breakdown (1 Full Week)

| Service | Usage | Cost |
|---------|-------|------|
| S3 | ~2GB storage, 1 week | ~$0.05 |
| Glue ETL job | 2 G.1X workers, ~5 mins | ~$0.30 |
| Glue Crawler | 2 crawls | ~$0.05 |
| Athena | 4 queries on Parquet | ~$0.10 |
| Lambda (Container Image) | Isolation Forest model | ~$0.00 (free tier) |
| ECR | Container image storage (~1 week, ~2GB) | ~$0.05 |
| EventBridge | Orchestration rules | ~$0.00 (free tier) |
| SNS | Alert emails | ~$0.00 |
| SQS (DLQ) | Lambda dead-letter queue | ~$0.00 |
| QuickSight | Dashboard (1 user, 30-day free) | ~$0.00 |
| Terraform state | S3 + DynamoDB | ~$0.05 |
| **Total** | **Full week** | **~$0.61** |

---

## Project Structure

```
payflow/
├── terraform/
│   ├── main.tf                    # Module orchestration
│   ├── variables.tf               # All variables (account_id, email, etc.)
│   ├── outputs.tf                 # Bucket names, role ARNs, topic ARNs
│   ├── backend.tf                 # S3 backend config
│   └── modules/
│       ├── s3/
│       │   ├── main.tf            # 5 buckets + versioning + public access blocks + EventBridge
│       │   └── variables.tf
│       ├── glue/
│       │   ├── main.tf            # Database + ETL job + 2 crawlers
│       │   └── variables.tf
│       ├── lake_formation/
│       │   ├── main.tf            # Data lake settings + resource registrations + database permissions
│       │   └── variables.tf
│       ├── athena/
│       │   ├── main.tf            # Workgroup with 1GB scan limit
│       │   └── variables.tf
│       ├── lambda/
│       │   ├── main.tf            # Lambda container function + SNS topic + SQS DLQ + policies
│       │   └── variables.tf
│       ├── eventbridge/
│       │   ├── main.tf            # 2 EventBridge rules + 2 Lambda trigger functions + permissions
│       │   └── variables.tf
│       └── iam/
│           ├── main.tf            # 3 roles (glue, lambda, eventbridge) + scoped policies
│           └── variables.tf
├── scripts/
│   ├── glue_etl_job.py            # Core ETL + feature engineering
│   ├── anomaly_lambda.py          # Isolation Forest ML model (container image)
│   ├── Dockerfile                  # Lambda container image definition
│   └── validate_data.py           # Dataset validation script
├── queries/
│   ├── daily_volume.sql
│   ├── fraud_merchants.sql
│   ├── settlement_report.sql
│   └── peak_hours.sql
├── data/
│   └── train_transaction.csv      # IEEE-CIS Fraud Detection dataset
├── .github/
│   └── workflows/
│       └── terraform.yml
└── payflow-implementation-plan.md # This file
```

---

## Complete Data Flow

```
Kaggle Dataset (IEEE-CIS Fraud Detection · 590K records · 394 columns)
            ↓
Upload raw CSV to S3 (no scaling needed)
            ↓
S3 Raw Zone  (payflow-raw-transactions-dev-104573823385/)
            ↓
S3 ObjectCreated Event → EventBridge Rule → Lambda (glue-trigger) → glue:start_job_run()
            ↓
Glue ETL Job (PySpark): Clean + Deduplicate + Enrich + Feature Engineering
            ↓
S3 Clean Zone (payflow-clean-transactions-dev-104573823385/clean/ · Parquet · partitioned by year/month/region)
            ↓
Glue Job Succeeds → EventBridge Rule → Lambda (crawler-trigger) → glue:startCrawler() ×2
            ↓
Glue Crawlers → Glue Data Catalog (payflow_db · 3 tables)
            ↓
(Manual Lambda invoke after crawlers finish — crawlers don't emit completion events)
            ↓
AWS Lambda Container Image (Isolation Forest anomaly scoring · reads only needed columns · extracts partition cols from S3 keys)
            ↓
S3 Scored Zone (payflow-scored-transactions-dev-104573823385/scored/ · Parquet · partitioned)
            ↓
SNS Alert (email with anomaly summary to kaushiik.23cs@kct.ac.in)
            ↓
Lambda on error → SQS Dead-Letter Queue
            ↓
Athena (SQL queries on scored data via payflow-workgroup)
            ↓
Amazon QuickSight (dashboard connected to Athena)
```

---

## Day 1 — Data + Infrastructure Setup

### Goal: Raw data in S3, all AWS infrastructure provisioned via Terraform

---

### Morning — Dataset Preparation

**Step 1: Download Dataset**
- Go to Kaggle → search **"IEEE-CIS Fraud Detection"**
- Download `train_transaction.csv` (~590K records, ~380MB)
- No scaling needed — use raw data directly

**Step 2: Quick data check**
```python
import pandas as pd

df = pd.read_csv('train_transaction.csv')
print(f"Records  : {len(df):,}")
print(f"Columns  : {df.columns.tolist()}")
print(f"Nulls    : {df.isnull().sum().sum():,}")
print(f"Fraud %  : {df['isFraud'].mean()*100:.2f}%")
```

---

### Afternoon — Terraform Setup

> **Bootstrap step (run once BEFORE terraform init):** The S3 backend bucket and DynamoDB lock table must exist before Terraform can use them. Run this first:
> ```bash
> # Create S3 bucket for Terraform state (MUST include account ID for uniqueness)
> aws s3api create-bucket --bucket payflow-tfstate-104573823385 --region ap-south-1 \
>   --create-bucket-configuration LocationConstraint=ap-south-1
> aws s3api put-bucket-versioning --bucket payflow-tfstate-104573823385 \
>   --versioning-configuration Status=Enabled
>
> # Create DynamoDB table for state locking
> aws dynamodb create-table \
>   --table-name payflow-terraform-lock \
>   --attribute-definitions AttributeName=LockID,AttributeType=S \
>   --key-schema AttributeName=LockID,KeyType=HASH \
>   --billing-mode PAY_PER_REQUEST \
>   --region ap-south-1
> ```

**Step 1: Backend configuration**
```hcl
# terraform/backend.tf
terraform {
  backend "s3" {
    bucket         = "payflow-tfstate-104573823385"
    key            = "state/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "payflow-terraform-lock"
    encrypt        = true
  }
}
```

**Step 2: Variables**
```hcl
# terraform/variables.tf
variable "aws_region"    { default = "ap-south-1" }
variable "env"           { default = "dev" }
variable "project_name"  { default = "payflow" }
variable "alert_email"   { default = "kaushiik.23cs@kct.ac.in" }
variable "account_id"    { default = "104573823385" }
```

**Step 3: S3 Buckets** (see `terraform/modules/s3/main.tf`)
- 5 buckets with `${var.account_id}` suffix for global uniqueness
- Versioning + public access blocks on all buckets
- **EventBridge notification enabled on raw bucket** (`eventbridge = true`)

**Step 4: IAM Roles** (see `terraform/modules/iam/main.tf`)
- 3 roles: `payflow-glue-role`, `payflow-lambda-role`, `payflow-eventbridge-role`
- **Least-privilege scoped inline policies** (NOT S3FullAccess/SNSFullAccess)
- Lambda role includes `sqs:SendMessage` for DLQ

**Step 5: Apply Terraform**
```bash
cd terraform
terraform init
terraform plan
terraform apply
```

**End of Day 1 Checklist**
- [ ] Bootstrap: S3 backend bucket + DynamoDB lock table created manually
- [ ] Kaggle dataset downloaded (590K records)
- [ ] All 5 S3 buckets created via Terraform with versioning + public access blocks
- [ ] IAM roles created with scoped least-privilege policies (not full access)
- [ ] S3 EventBridge notification enabled on raw bucket
- [ ] Raw CSV uploaded to S3
- [ ] EventBridge role + Lambda trigger roles created
- [ ] `terraform apply` runs with no errors

---

## Day 2 — AWS Glue ETL Pipeline

### Goal: 590K records cleaned, enriched, feature-engineered, stored as Parquet

---

### Glue ETL Script

> **Important:** The ETL writes to `s3://{CLEAN_BUCKET}/clean/` (with a prefix), not the bucket root. This avoids the "Can not create a Path from an empty string" error when partition columns have null values. The Parquet output is partitioned by `year`, `month`, `region`.

```python
# scripts/glue_etl_job.py
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import functions as F
from pyspark.sql.window import Window

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'RAW_BUCKET', 'CLEAN_BUCKET'])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

df = spark.read \
    .option("header", True) \
    .option("inferSchema", True) \
    .csv(f"s3://{args['RAW_BUCKET']}/train_transaction.csv")

print(f"Raw records loaded: {df.count():,}")

# ... feature engineering steps (see full script) ...

df = df.dropna(subset=['TransactionID', 'amount', 'card1'])
df = df.filter(F.col('region').isNotNull() & F.col('month').isNotNull() & F.col('day').isNotNull())

clean_count = df.count()
print(f"Clean records after ETL: {clean_count:,}")

if clean_count == 0:
    print("WARNING: No records after ETL. Skipping write.")
else:
    df.write \
      .mode('overwrite') \
      .partitionBy('year', 'month', 'region') \
      .parquet(f"s3://{args['CLEAN_BUCKET']}/clean/")

print("ETL job complete.")
job.commit()
```

### Deploy & Run

```bash
# Upload ETL script to S3
aws s3 cp scripts/glue_etl_job.py s3://payflow-glue-scripts-dev-104573823385/

# Trigger Glue job
aws glue start-job-run --job-name payflow-etl-job --region ap-south-1

# Wait for completion (~5 mins), then run crawlers
aws glue start-crawler --name payflow-clean-crawler --region ap-south-1
# After clean crawler completes:
aws glue start-crawler --name payflow-scored-crawler --region ap-south-1
```

**End of Day 2 Checklist**
- [ ] Glue ETL job completes successfully (~5 min)
- [ ] Parquet files visible in `clean/` prefix in clean S3 bucket
- [ ] Partitions: year / month / region
- [ ] Glue Crawlers populated `payflow_db` in Data Catalog
- [ ] All feature columns present in output schema

---

## Day 3 — Lake Formation + Athena

### Goal: Data lake governed, business queries working in Athena

---

### Lake Formation

> **Key discovery:** Table-level permissions fail when tables don't exist yet. Use **database-level permissions** instead, and add table-level permissions after crawlers create the tables.

```hcl
# terraform/modules/lake_formation/main.tf
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
  database { name = "payflow_db" }
}

resource "aws_lakeformation_permissions" "analyst_database" {
  principal   = var.analyst_role_arn
  permissions = ["DESCRIBE"]
  database { name = "payflow_db" }
}
```

### Athena Queries

> **Note:** The Glue Crawler names tables based on the S3 path. The clean data table will be named `payflow_clean_transactions_dev_104573823385` (derived from the bucket name), not `clean_transactions`. Update your queries accordingly.

```sql
-- queries/daily_volume.sql
SELECT year, month, day, COUNT(*) AS txn_count,
       ROUND(SUM(amount), 2) AS total_amount, ROUND(AVG(amount), 2) AS avg_amount
FROM payflow_db.payflow_clean_transactions_dev_104573823385
GROUP BY year, month, day ORDER BY year, month, day;

-- queries/fraud_merchants.sql
SELECT ProductCD AS merchant_category, COUNT(*) AS suspicious_txns,
       ROUND(SUM(amount), 2) AS total_suspicious_amount,
       ROUND(AVG(amount_deviation), 4) AS avg_deviation
FROM payflow_db.payflow_clean_transactions_dev_104573823385
WHERE geo_flag = 1 AND amount_bucket = 'high'
GROUP BY ProductCD ORDER BY suspicious_txns DESC LIMIT 20;

-- queries/peak_hours.sql
SELECT transaction_hour, COUNT(*) AS txn_volume,
       ROUND(AVG(amount), 2) AS avg_amount, SUM(geo_flag) AS geo_flagged_count
FROM payflow_db.payflow_clean_transactions_dev_104573823385
GROUP BY transaction_hour ORDER BY transaction_hour;
```

**End of Day 3 Checklist**
- [ ] Lake Formation registered and governing clean + scored S3 paths
- [ ] Database-level permissions configured (admin: ALL, analyst: DESCRIBE)
- [ ] All 4 Athena queries saved and returning correct results
- [ ] Athena workgroup with 1GB scan limit (cost protection)

---

## Day 4 — Lambda Anomaly Detection + EventBridge Orchestration

### Goal: Isolation Forest scoring every transaction, SNS alert fired, pipeline orchestrated end-to-end

---

### Key Discoveries & Fixes

> **1. EventBridge cannot directly target Glue jobs or crawlers.** Both return 400 errors. The fix is to use **Lambda intermediary functions** (`payflow-glue-trigger` and `payflow-crawler-trigger`) that call `glue:start_job_run()` and `glue:startCrawler()` respectively.
>
> **2. `AWS_REGION` is a reserved Lambda environment variable.** Use `REGION` instead.
>
> **3. Docker image must be built for `linux/amd64`.** Lambda runs on x86_64. Use `docker buildx build --platform linux/amd64 --provenance=false` to avoid multi-arch manifest issues.
>
> **4. S3 `GetObject` Body is a streaming object.** `pd.read_parquet(resp['Body'])` fails with `UnsupportedOperation: seek`. Read the body bytes first: `pd.read_parquet(io.BytesIO(resp['Body'].read()))`.
>
> **5. Partition columns aren't stored in Parquet data.** When reading partitioned data with `pd.read_parquet(columns=[...])`, you cannot project partition columns like `year`, `month`, `region`. Extract them from the S3 key paths instead.

---

### Lambda Function Code

```python
# scripts/anomaly_lambda.py
import boto3, io, os, json, traceback
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

s3  = boto3.client('s3')
sns = boto3.client('sns', region_name=os.environ['REGION'])  # NOT AWS_REGION

CLEAN_BUCKET  = os.environ['CLEAN_BUCKET']
SCORED_BUCKET = os.environ['SCORED_BUCKET']
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']

# Only project columns that actually exist in the Parquet data files
# Partition columns (year, month, region) are extracted from S3 key paths
COLUMNS = [
    'TransactionID', 'TransactionAmt', 'card1', 'addr1', 'addr2',
    'ProductCD', 'TransactionDT', 'amount', 'card_masked',
    'transaction_hour', 'is_weekend', 'amount_bucket',
    'txn_velocity', 'merchant_avg_amount', 'amount_deviation',
    'geo_flag', 'day'
]

def _read_parquet_from_bucket(bucket):
    paginator = s3.get_paginator('list_objects_v2')
    dfs = []
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if key.endswith('.parquet'):
                resp = s3.get_object(Bucket=bucket, Key=key)
                body_bytes = resp['Body'].read()  # Read full body (not stream)
                chunk = pd.read_parquet(io.BytesIO(body_bytes), columns=COLUMNS)
                # Extract partition columns from S3 key path
                part_year = int(key.split('year=')[1].split('/')[0])
                part_month = int(key.split('month=')[1].split('/')[0])
                part_region = key.split('region=')[1].split('/')[0]
                chunk['year'] = part_year
                chunk['month'] = part_month
                chunk['region'] = part_region
                dfs.append(chunk)
                del resp, body_bytes, chunk
    if not dfs:
        raise ValueError(f"No Parquet files found in s3://{bucket}/")
    return pd.concat(dfs, ignore_index=True)

def lambda_handler(event, context):
    try:
        df = _read_parquet_from_bucket(CLEAN_BUCKET)
        # ... feature engineering + Isolation Forest scoring ...
        # Write scored data partitioned to S3
        for (year_val, month_val, region_val), group in df_scored.groupby(['year', 'month', 'region']):
            partition_key = f"scored/year={int(year_val)}/month={int(month_val)}/region={region_val}/scored.parquet"
            buffer = io.BytesIO()
            group.drop(columns=['year', 'month', 'region']).to_parquet(buffer, index=False)
            buffer.seek(0)
            s3.put_object(Bucket=SCORED_BUCKET, Key=partition_key, Body=buffer.getvalue())
        # SNS alert with summary
        sns.publish(TopicArn=SNS_TOPIC_ARN, Subject='[PayFlow] Anomaly Detection Complete', Message=...)
        return {'statusCode': 200, 'body': json.dumps({...})}
    except Exception as e:
        print(f"ERROR: {traceback.format_exc()}")
        raise e
```

### Dockerfile

```dockerfile
# scripts/Dockerfile
FROM public.ecr.aws/lambda/python:3.12

RUN pip install --no-cache-dir \
    scikit-learn==1.5.0 \
    pandas==2.2.2 \
    numpy==1.26.4 \
    pyarrow==16.1.0

COPY anomaly_lambda.py ${LAMBDA_TASK_ROOT}

CMD [ "anomaly_lambda.lambda_handler" ]
```

> **Important:** Must build with `docker buildx build --platform linux/amd64 --provenance=false` to avoid multi-arch manifest issues with Lambda. The `--provenance=false` flag prevents attestation manifests that Lambda doesn't support.

### Build & Push ECR Image

```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin 104573823385.dkr.ecr.ap-south-1.amazonaws.com

# Create ECR repository (first time only)
aws ecr create-repository --repository-name payflow-anomaly-detector --region ap-south-1

# Build for linux/amd64 (Lambda architecture) — CRITICAL FLAGS
docker buildx build --platform linux/amd64 --provenance=false \
  -t 104573823385.dkr.ecr.ap-south-1.amazonaws.com/payflow-anomaly-detector:latest --push .
```

### EventBridge Orchestration (Lambda Intermediaries)

> **Why Lambda intermediaries?** EventBridge cannot directly target Glue jobs or crawlers — it returns a 400 error. Small Lambda proxy functions call `glue:start_job_run()` and `glue:startCrawler()` on behalf of EventBridge rules.

```hcl
# terraform/modules/eventbridge/main.tf
# (simplified — see actual file for full code)

# Lambda: S3 upload → start Glue job
resource "aws_lambda_function" "glue_trigger" {
  function_name = "${var.project_name}-glue-trigger"
  runtime       = "python3.12"
  handler       = "lambda_function.lambda_handler"
  role          = aws_iam_role.glue_trigger_role.arn
  filename      = data.archive_file.glue_trigger_lambda_zip.output_path
  # Calls glue.start_job_run(JobName='payflow-etl-job')
}

# Lambda: Glue success → start both crawlers
resource "aws_lambda_function" "crawler_trigger" {
  function_name = "${var.project_name}-crawler-trigger"
  runtime       = "python3.12"
  handler       = "lambda_function.lambda_handler"
  role          = aws_iam_role.glue_trigger_role.arn
  filename     = data.archive_file.crawler_trigger_lambda_zip.output_path
  # Calls glue.start_crawler(Name='payflow-clean-crawler') & 'payflow-scored-crawler'
}

# EventBridge Rule 1: S3 raw upload → glue_trigger Lambda
resource "aws_cloudwatch_event_rule" "s3_upload_trigger" { ... }

# EventBridge Rule 2: Glue job success → crawler_trigger Lambda
resource "aws_cloudwatch_event_rule" "glue_success_trigger" { ... }
```

### End-to-End Pipeline Run

```bash
# Build & push Lambda container image (see Dockerfile section above)

# Upload data
aws s3 cp train_transaction.csv s3://payflow-raw-transactions-dev-104573823385/

# Option A: S3 upload triggers EventBridge → glue_trigger Lambda → Glue ETL job
# Option B: Manual trigger
aws glue start-job-run --job-name payflow-etl-job --region ap-south-1

# After Glue job completes (~5 min), crawlers start automatically via EventBridge
# Or run manually:
aws glue start-crawler --name payflow-clean-crawler --region ap-south-1
# After clean crawler:
aws glue start-crawler --name payflow-scored-crawler --region ap-south-1

# After crawlers complete, invoke Lambda manually:
aws lambda invoke --function-name payflow-anomaly-detector --region ap-south-1 \
  --cli-binary-format raw-in-base64-out --payload '{}' response.json

# Expected output:
# {"statusCode":200,"body":"{\"total_scored\":590540,\"anomalies_detected\":11811,\"anomaly_rate_pct\":2.0}"}
```

**End of Day 4 Checklist**
- [ ] Lambda container image built with `--platform linux/amd64 --provenance=false`
- [ ] Lambda deployed via Terraform with DLQ + SNS configured
- [ ] Lambda reads ALL partitioned Parquet files via S3 paginator (not just one)
- [ ] Lambda extracts partition columns from S3 key paths (not Parquet column projection)
- [ ] Lambda uses `REGION` env var (not `AWS_REGION` — which is reserved)
- [ ] Lambda reads S3 body bytes into BytesIO (not streaming Body)
- [ ] Lambda writes scored data partitioned by year/month/region
- [ ] `anomaly_score` and `is_anomaly` columns in scored output
- [ ] `top_anomalies.csv` exported to S3
- [ ] SNS alert email received at kaushiik.23cs@kct.ac.in
- [ ] EventBridge Rule 1: S3 upload → glue_trigger Lambda (working)
- [ ] EventBridge Rule 2: Glue success → crawler_trigger Lambda (working)
- [ ] Scored table visible in Athena Data Catalog
- [ ] IAM policies are scoped (least-privilege, no S3FullAccess)
- [ ] Lambda container cold start tested (expect 45-60s on first invoke)

---

## Day 5 — QuickSight Dashboard + Polish + Demo

### Goal: Dashboard live, project documented, demo-ready

---

### Amazon QuickSight Dashboard Setup

> **Why QuickSight instead of Looker Studio?** AWS Athena does not have a native connector in Google Looker Studio. QuickSight connects directly to Athena with zero data movement, making it the natural choice for an AWS-native pipeline.

**Step 1: Sign up for QuickSight**
1. Go to **AWS Console → QuickSight** (or https://quicksight.aws.amazon.com)
2. Select **Standard** edition (free for 30 days, then $9/month)
3. Region: `ap-south-1`
4. Under AWS permissions, enable: Athena, S3, IAM

**Step 2: Create Dataset from Athena**
1. QuickSight → **Datasets → New dataset → Athena**
2. Data source name: `payflow-athena`
3. Database: `payflow_db` → Table: `scored`
4. Choose **Direct SQL query** (not SPICE for large datasets)
5. Click **Visualize**

**Step 3: Create Dashboard Charts**

| Panel | Chart Type | Field Mapping |
|-------|-----------|---------------|
| Anomaly Score Distribution | Histogram | anomaly_score |
| Anomalies by Product Category | Horizontal bar | productcd vs SUM(is_anomaly) |
| Top Fraud Transactions | Table | transactionid, amount, anomaly_score, productcd, transaction_hour (filtered: is_anomaly=1) |
| Anomalies by Region | Pie chart | region vs SUM(is_anomaly) |
| Amount vs Anomaly Score | Scatter plot | amount (X) vs anomaly_score (Y), color: is_anomaly |
| KPI Scorecards | KPI | AVG(anomaly_score), SUM(is_anomaly) |

**Step 4: Add Filters**
- Drop-down: `amount_bucket` (low/medium/high)
- Drop-down: `region`
- Date range: `day`

**Step 5: Publish**
- Click **Share → Publish dashboard**
- Share via email or AWS SSO

---

### Evening — Documentation + CI/CD

**GitHub Actions:** (see `.github/workflows/terraform.yml`)

**README.md must include:**
- Architecture diagram
- Tech stack table
- Step-by-step setup guide (including ECR build with `--platform linux/amd64`)
- Sample Athena query output (screenshots)
- QuickSight dashboard link
- Anomaly detection results summary (590,540 scored, 11,811 anomalies, 2.00% rate)

---

## Full Tech Stack

| Layer | Technology | Cost |
|-------|-----------|------|
| Infrastructure | Terraform | Free |
| Orchestration | EventBridge + Lambda intermediary functions | ~$0.00 (free tier) |
| Storage | Amazon S3 | ~$0.05 |
| ETL | AWS Glue PySpark (2 G.1X workers) | ~$0.30 |
| Cataloging | Glue Crawler + Data Catalog | ~$0.05 |
| Governance | AWS Lake Formation (database-level permissions) | Free |
| Querying | Amazon Athena | ~$0.10 |
| ML | AWS Lambda Container Image + Isolation Forest | ~$0.00 (free tier) |
| Container Registry | Amazon ECR (~2GB image) | ~$0.05 |
| Error Handling | SQS Dead-Letter Queue | ~$0.00 |
| Alerts | Amazon SNS | ~$0.00 |
| Dashboard | Amazon QuickSight | ~$0.00 (30-day free) |
| CI/CD | GitHub Actions | Free |
| **Total** | **1 full week** | **~$0.61** |

---

## Security Checklist

- [ ] No hardcoded AWS credentials — IAM roles only
- [ ] No hardcoded bucket names or ARNs in Lambda — environment variables (`CLEAN_BUCKET`, `SCORED_BUCKET`, `SNS_TOPIC_ARN`, `REGION`)
- [ ] `AWS_REGION` env var NOT used (reserved by Lambda) — uses `REGION` instead
- [ ] Terraform state encrypted in S3 with DynamoDB locking
- [ ] S3 bucket names include `account_id` suffix for global uniqueness
- [ ] S3 EventBridge notifications explicitly enabled on raw bucket (`eventbridge = true`)
- [ ] All IAM roles follow least-privilege principle (scoped S3/SNS/SQS policies, not full access)
- [ ] Lambda role includes `sqs:SendMessage` for DLQ
- [ ] Card numbers masked in ETL — never stored in plain text
- [ ] Lake Formation database-level permissions (not table-level — tables don't exist at deploy time)
- [ ] S3 buckets have versioning enabled + public access blocked
- [ ] Athena workgroup has 1GB scan limit per query (cost protection)
- [ ] Lambda has DLQ configured for failed invocations
- [ ] EventBridge rules use Lambda intermediary functions (Glue/Crawler direct targets return 400)
- [ ] Lambda uses `n_jobs=1` (single vCPU environment)

---

## Key Fixes from Original Plan

| # | Issue | Fix | Discovered During |
|---|-------|-----|-------------------|
| 1 | Lambda zip exceeds 250MB (sklearn + pandas) | Use **Container Image** deployment via ECR | Day 4 |
| 2 | Lambda reads only one Parquet file | `_read_all_parquet_from_bucket()` reads ALL files via S3 paginator | Day 4 |
| 3 | EventBridge cannot directly target Glue jobs/crawlers | Use **Lambda intermediary functions** (`glue-trigger`, `crawler-trigger`) that call `glue:start_job_run()` and `glue:startCrawler()` | Day 1 `terraform apply` |
| 4 | `AWS_REGION` is a reserved Lambda env var | Use `REGION` instead | Day 4 `terraform apply` |
| 5 | Docker image must be `linux/amd64` only | Build with `docker buildx build --platform linux/amd64 --provenance=false` | Day 4 ECR push |
| 6 | Multi-arch Docker manifest not supported by Lambda | Use `--provenance=false` flag in `docker buildx build` | Day 4 Lambda creation |
| 7 | S3 `GetObject` Body stream doesn't support `seek()` | Read body bytes first: `pd.read_parquet(io.BytesIO(resp['Body'].read()))` | Day 4 Lambda invoke |
| 8 | Parquet column projection fails for partition columns | Extract `year`, `month`, `region` from S3 key paths instead of `pd.read_parquet(columns=[...])` | Day 4 Lambda invoke |
| 9 | Lambda OOM with 590K records × 394 columns | Read only needed columns via `COLUMNS` list, write scored data in partitions | Day 4 Lambda invoke |
| 10 | Glue ETL `parquet()` write fails with empty path | Write to `clean/` prefix, filter null partitions before write | Day 2 Glue job |
| 11 | Lake Formation table permissions fail before tables exist | Use **database-level** permissions (`ALL` for admin, `DESCRIBE` for analyst) instead of table-level | Day 3 `terraform apply` |
| 12 | `eventbridge = true` in S3 bucket notification | Use as argument, not block (Terraform AWS provider v5+ syntax) | Day 1 `terraform plan` |
| 13 | Lambda role needs SQS SendMessage for DLQ | Add `sqs:SendMessage` to Lambda IAM policy alongside `sns:Publish` | Day 4 `terraform apply` |
| 14 | Glue Crawler completion doesn't emit events | Invoke Lambda manually after crawler finishes (or use Step Functions) | Design |
| 15 | Lambda cold start ~45-60s for container image | Expected behavior; invoke once for warmup before demos | Day 4 |
| 16 | Google Looker Studio has no AWS Athena connector | Use **Amazon QuickSight** instead (native Athena connector) | Day 5 |

---

## Actual Pipeline Results

```
Glue ETL:     590,540 records processed, partitioned by year/month/region into Parquet
Crawlers:     3 tables in payflow_db (clean, scored, top_anomalies_csv)
Lambda ML:    590,540 records scored, 11,811 anomalies flagged (2.00% rate)
SNS Alert:    Email sent to kaushiik.23cs@kct.ac.in
Athena:       All 4 queries returning correct results
QuickSight:   Dashboard setup via AWS native BI tool
```

---

## Labs from Syllabus Covered

| Lab No. | Lab Name | Used Where |
|---------|----------|-----------|
| 8 | RESTful API with Lambda + API Gateway | Lambda anomaly trigger |
| 9 | Lambda + DynamoDB | Lambda execution |
| 12 | S3 event triggers + Lambda | EventBridge → Lambda → Glue orchestration |
| 13 | Data ingestion using Glue + S3 | Day 2 — ETL pipeline |
| 14 | Glue Crawler | Day 2 — Auto-catalog data |
| 15 | Amazon Athena | Day 3 — Business queries |
| 16 | Columnar formats + cost optimization | Day 2 — Parquet output |
| 17 | AWS Lake Formation | Day 3 — Data lake governance |
| 18 | AWS Glue DataBrew | Day 2 — Data preparation |
| 19 | Amazon QuickSight | Day 5 — Dashboard |
| 25 | Cost optimization | Parquet + partition pruning + ECR |

---

*PayFlow — Built by Kaushiik Arul | github.com/Kaushiik-13/PayFlow*