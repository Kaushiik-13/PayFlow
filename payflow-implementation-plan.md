# PayFlow — Payment Transaction Anomaly Detection Pipeline
### Implementation Plan | Cost-Optimized | ~$1.13 for 1 Week

> **By Kaushiik Arul** | Cloud & Data Engineering Project  
> Stack: AWS S3 · Glue · Lake Formation · Athena · Lambda · EventBridge · SNS · QuickSight · API Gateway · CloudFront · Terraform

---

## Project Summary

PayFlow is an **end-to-end, source-agnostic** cloud-scale ETL pipeline that accepts **any payment transaction dataset** (CSV, Parquet, or JSON) via a **web upload portal**, automatically detects column roles and applies smart feature engineering, processes and enriches data through AWS Glue, governs access via Lake Formation, and runs an **unsupervised Isolation Forest ML model on AWS Lambda Container Image** to automatically detect fraudulent anomalies — without needing labeled data or a fixed schema. The pipeline is **orchestrated via EventBridge + Lambda intermediary functions**: S3 upload (via browser or CLI) triggers a Glue trigger Lambda (which starts the Glue job), Glue completion triggers a Crawler trigger Lambda (which starts both crawlers), and Lambda is invoked manually after crawlers finish. Results are **visible in the web portal** and queryable via Athena and QuickSight with real-time SNS alerts.

**Key Design Decisions:**
- **Source-agnostic ETL**: Auto-detects column roles (transaction ID, amount, timestamp, etc.) using heuristics — no hardcoded schema
- **Multi-format input**: Supports CSV, Parquet, and JSON files
- **Web upload portal**: S3 static website + CloudFront, uploads via presigned URLs directly to S3
- **Pipeline visibility**: Frontend polls API Gateway for real-time pipeline status and anomaly detection results
- **Auto-trigger**: EventBridge rule on S3 upload automatically starts the pipeline

---

## Cost Breakdown (1 Full Week)

| Service | Usage | Cost |
|---------|-------|------|
| S3 | ~2GB storage, 1 week | ~$0.05 |
| S3 Website Bucket | Frontend hosting | ~$0.01 |
| CloudFront | Frontend CDN | ~$0.50 |
| Glue ETL job | 2 G.1X workers, ~5 mins | ~$0.30 |
| Glue Crawler | 2 crawls | ~$0.05 |
| Athena | 4 queries on Parquet | ~$0.10 |
| Lambda (Container Image) | Isolation Forest model | ~$0.00 (free tier) |
| ECR | Container image storage (~1 week, ~2GB) | ~$0.05 |
| EventBridge | Orchestration rules | ~$0.00 (free tier) |
| SNS | Alert emails | ~$0.00 |
| SQS (DLQ) | Lambda dead-letter queue | ~$0.00 |
| API Gateway | 3 routes (upload-url, pipeline-status, results) | ~$0.01 (free tier) |
| API Lambdas | 3 Python zip functions (presigned, status, results) | ~$0.00 (free tier) |
| QuickSight | Dashboard (1 user, 30-day free) | ~$0.00 |
| Terraform state | S3 + DynamoDB | ~$0.05 |
| **Total** | **Full week** | **~$1.13** |

---

## Project Structure

```
payflow/
├── frontend/
│   ├── index.html                    # Upload portal (3 panels: upload, status, results)
│   ├── styles.css                    # Styling with status indicators
│   └── app.js                        # API calls, drag-and-drop, polling, results rendering
├── terraform/
│   ├── main.tf                       # Module orchestration (10 modules)
│   ├── variables.tf                  # All variables (account_id, email, etc.)
│   ├── outputs.tf                    # Bucket names, role ARNs, topic ARNs, frontend URL, API URL
│   ├── backend.tf                    # S3 backend config
│   └── modules/
│       ├── s3/
│       │   ├── main.tf               # 6 buckets + versioning + public access blocks + EventBridge + CORS + website
│       │   └── variables.tf
│       ├── glue/
│       │   ├── main.tf               # Database + ETL job + 2 crawlers
│       │   └── variables.tf
│       ├── lake_formation/
│       │   ├── main.tf               # Data lake settings + resource registrations + database permissions
│       │   └── variables.tf
│       ├── athena/
│       │   ├── main.tf               # Workgroup with 1GB scan limit
│       │   └── variables.tf
│       ├── lambda/
│       │   ├── main.tf               # Lambda container function + SNS topic + SQS DLQ + policies
│       │   └── variables.tf
│       ├── eventbridge/
│       │   ├── main.tf               # 2 EventBridge rules + 2 Lambda trigger functions + permissions
│       │   └── variables.tf
│       ├── iam/
│       │   ├── main.tf               # 4 roles (glue, lambda, eventbridge, api) + scoped policies
│       │   └── variables.tf
│       ├── api_gateway/
│       │   ├── main.tf               # REST API + 3 routes + CORS + deployment
│       │   └── variables.tf
│       ├── api_lambdas/
│       │   ├── main.tf               # 3 Lambda functions (presigned, status, results) + IAM roles
│       │   └── variables.tf
│       └── frontend/
│           ├── main.tf               # S3 website bucket + CloudFront distribution
│           └── variables.tf
├── scripts/
│   ├── schema_utils.py               # Auto-detection engine (column roles, format, validation)
│   ├── glue_etl_job.py               # Core ETL + dynamic feature engineering (source-agnostic)
│   ├── anomaly_lambda.py             # Isolation Forest ML model (dynamic features + _summary.json)
│   ├── presigned_url_lambda.py       # Generate presigned PUT URLs for browser uploads
│   ├── pipeline_status_lambda.py     # Check Glue/crawler/scored pipeline status
│   ├── results_lambda.py             # Fetch _summary.json + top_anomalies.csv from S3
│   ├── Dockerfile                     # Lambda container image definition
│   ├── upload_to_s3.py               # Upload any file format to S3 (CLI helper)
│   └── validate_data.py              # Generic dataset validation (auto-detect columns)
├── queries/
│   ├── daily_volume.sql
│   ├── fraud_merchants.sql
│   ├── settlement_report.sql
│   └── peak_hours.sql
├── data/
│   └── train_transaction.csv         # IEEE-CIS Fraud Detection dataset (example source)
├── .github/
│   └── workflows/
│       └── terraform.yml
└── payflow-implementation-plan.md    # This file
```

---

## Complete Data Flow

```
Any Data Source (CSV / Parquet / JSON)
            ↓
Browser Upload Portal ──POST /upload-url──► API Gateway ──► Presigned URL Lambda
            ↓                                                      │
   PUT file to Presigned S3 URL ◄────────────────────────────────┘
            ↓
S3 Raw Zone (payflow-raw-transactions-dev-104573823385/)
            ↓
S3 ObjectCreated Event → EventBridge Rule → Lambda (glue-trigger) → glue:start_job_run()
            ↓
Glue ETL Job (PySpark): Auto-detect format → Infer column roles → Clean + Deduplicate + Feature Engineering
            ↓
S3 Clean Zone (payflow-clean-transactions-dev-104573823385/clean/ · Parquet · partitioned by year/month/region)
   + _schema.json (detected column mappings + metadata)
            ↓
Glue Job Succeeds → EventBridge Rule → Lambda (crawler-trigger) → glue:startCrawler() ×2
            ↓
Glue Crawlers → Glue Data Catalog (payflow_db · 3 tables)
            ↓
(Metadata Lambda invoke after crawlers finish — crawlers don't emit completion events)
            ↓
Lambda Container Image: Read _schema.json → Build dynamic feature matrix → Isolation Forest scoring
   + writes _summary.json to scored bucket
            ↓
S3 Scored Zone (payflow-scored-transactions-dev-104573823385/scored/ · Parquet · partitioned)
   + top_anomalies.csv
   + _summary.json
            ↓
GET /pipeline-status ──► API Gateway ──► Status Lambda ──► Checks Glue/Crawler/S3 states
GET /results ──► API Gateway ──► Results Lambda ──► Reads _summary.json + top_anomalies.csv
            ↓
Browser Portal: Upload panel ──► Status panel ──► Results panel
            ↓
(Also: SNS Alert, Athena, QuickSight as before)
```

---

## Day 1 — Data + Infrastructure Setup

### Goal: Raw data in S3, all AWS infrastructure provisioned via Terraform

---

### Morning — Dataset Preparation

**Step 1: Prepare Your Dataset**

The pipeline is **source-agnostic** — it works with any payment transaction dataset in CSV, Parquet, or JSON format. You can use the IEEE-CIS dataset as an example:

- Go to Kaggle → search **"IEEE-CIS Fraud Detection"**
- Download `train_transaction.csv` (~590K records, ~380MB)

**Step 2: Quick data check**
```python
import pandas as pd

df = pd.read_csv('train_transaction.csv')
print(f"Records  : {len(df):,}")
print(f"Columns  : {df.columns.tolist()}")
print(f"Nulls    : {df.isnull().sum().sum():,}")
print(f"Fraud %  : {df['isFraud'].mean()*100:.2f}%")
```

> **Note:** The pipeline will auto-detect column roles regardless of your dataset's column names. See the Auto-Detection Engine section below for details.

---

### Auto-Detection Engine (Source-Agnostic Pipeline)

The pipeline previously hardcoded column names for the IEEE-CIS dataset (`TransactionID`, `TransactionAmt`, `card1`, etc.). It now uses **auto-detection with smart defaults** via `scripts/schema_utils.py`.

**Column Role Detection Heuristics:**

| Canonical Role | Detection Heuristic |
|---------------|-------------------|
| `transaction_id` | Columns named `*id*`, `*txn*id*`, or first unique integer column |
| `amount` | Columns named `*amt*`, `*amount*`, `*price*`, `*total*`, `*value*`, `*sum*`, or first float column with all positive values |
| `timestamp` | Columns named `*date*`, `*time*`, `*dt*`, `*timestamp*`, or columns with datetime patterns |
| `card_number` | Columns named `*card*`, `*pan*`, `*account*`, or long integer columns |
| `address` | Columns named `*addr*`, `*city*`, `*state*`, `*zip*`, `*region*`, `*country*` |
| `product_code` | Columns named `*product*`, `*category*`, `*merchant*`, `*type*`, or low-cardinality string columns |

**Detection priority:** Exact name match → partial keyword match → statistical/heuristic fallback.

**Minimum Requirements:** The pipeline needs at least a `transaction_id` and `amount` column to function. All other columns are optional — feature engineering is conditional on what's detected.

**Override Mechanism:** Override auto-detection by passing `--OVERRIDE_MAPPINGS` to Glue or `OVERRIDE_MAPPINGS` env var to Lambda (JSON string mapping canonical names to source column names):
```json
{"transaction_id": "my_txn_id", "amount": "transaction_value", "timestamp": "created_at"}
```

**Conditional Feature Engineering:** Features are computed only if the required source columns are detected:

| Feature | Required Source Columns | Fallback |
|---------|------------------------|----------|
| `card_masked` | `card_number` | Skipped if not detected |
| `transaction_hour` | `timestamp` (parsed to hours) | Skipped if not detected |
| `is_weekend` | `timestamp` (day-of-week) | Skipped if not detected |
| `amount_bucket` | `amount` | Always computed (core feature) |
| `txn_velocity` | `transaction_id` + `transaction_hour` | Skipped if timestamp not detected |
| `merchant_avg_amount` | `product_code` + `amount` | Skipped if product_code not detected |
| `amount_deviation` | `amount` + `merchant_avg_amount` | Skipped if product_code not detected |
| `geo_flag` | `address_1` + `address_2` | Skipped if addresses not detected |

**Partition Columns:** Generated from available data:
- If `timestamp` detected → extract `year`, `month`, `day`
- If not → use defaults (`year=2024`, `month` from hash of ID, `day` from hash of ID)
- `region` → detected from address columns, or synthetic hash of `transaction_id % 3`

---

### Afternoon — Terraform Setup

> **Bootstrap step (run once BEFORE terraform init):** The S3 backend bucket and DynamoDB lock table must exist before Terraform can use them. Run this first:
> ```bash
> # Create S3 bucket for Terraform state (MUST include account ID for uniqueness)
> aws s3api create-bucket --bucket payflow-tfstate-104573823385 --region ap-south-1 \
>   --create-_bucket-configuration LocationConstraint=ap-south-1
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
- 6 buckets with `${var.account_id}` suffix for global uniqueness:
  - `payflow-raw-transactions-dev-104573823385` (raw data)
  - `payflow-clean-transactions-dev-104573823385` (clean data)
  - `payflow-scored-transactions-dev-104573823385` (scored data)
  - `payflow-athena-results-dev-104573823385` (Athena query results)
  - `payflow-glue-scripts-dev-104573823385` (Glue scripts)
  - `payflow-frontend-dev-104573823385` (frontend static website)
- Versioning + public access blocks on all buckets
- **EventBridge notification enabled on raw bucket** (`eventbridge = true`)
- **CORS configuration on raw bucket** (allows browser PUT from CloudFront + localhost)
- **Website configuration on frontend bucket** (index.html as index document)

**Step 4: IAM Roles** (see `terraform/modules/iam/main.tf`)
- 4 roles: `payflow-glue-role`, `payflow-lambda-role`, `payflow-eventbridge-role`, `payflow-api-role`
- **Least-privilege scoped inline policies** (NOT S3FullAccess/SNSFullAccess)
- Lambda role includes `sqs:SendMessage` for DLQ
- API Lambda role includes scoped S3/Glue permissions per function

**Step 5: Apply Terraform**
```bash
cd terraform
terraform init
terraform plan
terraform apply
```

**End of Day 1 Checklist**
- [ ] Bootstrap: S3 backend bucket + DynamoDB lock table created manually
- [ ] Dataset downloaded or prepared (any CSV/Parquet/JSON works)
- [ ] All 6 S3 buckets created via Terraform with versioning + public access blocks
- [ ] IAM roles created with scoped least-privilege policies (not full access)
- [ ] S3 EventBridge notification enabled on raw bucket
- [ ] CORS configuration on raw bucket for browser presigned URL uploads
- [ ] Frontend S3 bucket configured with website hosting
- [ ] API Gateway created with 3 routes (no auth, CORS enabled)
- [ ] 3 API Lambda functions deployed (presigned, status, results)
- [ ] CloudFront distribution serving frontend
- [ ] `terraform apply` runs with no errors

---

## Day 2 — AWS Glue ETL Pipeline (Source-Agnostic)

### Goal: Dynamic ETL that accepts any data source, infers column roles, and produces clean Parquet

---

### Source-Agnostic Glue ETL Script

> **Key Changes from V1:** The ETL no longer hardcodes `train_transaction.csv` or specific column names. It discovers data files in the raw bucket, detects the format, infers column roles, and conditionally applies feature engineering.

```python
# scripts/glue_etl_job.py
import sys
import json
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import StringType

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'RAW_BUCKET', 'CLEAN_BUCKET',
    'SOURCE_CONFIG'  # Optional: JSON override for column mappings
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

raw_bucket = args['RAW_BUCKET']
clean_bucket = args['CLEAN_BUCKET']
override_mappings = json.loads(args.get('SOURCE_CONFIG', '{}'))

# ─── Step 1: Discover data files in the raw bucket ───
from pyspark.sql.types import ArrayType, StringType
import re

hadoop_conf = sc._jsc.hadoopConfiguration()
fs = sc._jvm.org.apache.hadoop.fs.FileSystem.get(
    sc._jsc.hadoopConfiguration()
)
raw_path = sc._jvm.org.apache.hadoop.fs.Path(f"s3://{raw_bucket}/")
data_files = []

for f in fs.listStatus(raw_path):
    name = f.getPath().getName()
    if name.endswith(('.csv', '.parquet', '.json')):
        data_files.append(f.getPath().toString())

if not data_files:
    raise ValueError(f"No data files (.csv/.parquet/.json) found in s3://{raw_bucket}/")

# Use the first data file found
data_path = data_files[0]
file_ext = data_path.rsplit('.', 1)[-1].lower()
print(f"Auto-detected data file: {data_path} (format: {file_ext})")

# ─── Step 2: Read the data based on detected format ───
if file_ext == 'csv':
    df = spark.read.option("header", True).option("inferSchema", True).csv(data_path)
elif file_ext == 'parquet':
    df = spark.read.parquet(data_path)
elif file_ext == 'json':
    df = spark.read.option("multiline", True).json(data_path)
else:
    raise ValueError(f"Unsupported format: {file_ext}")

raw_count = df.count()
print(f"Raw records loaded: {raw_count:,}")

# ─── Step 3: Infer column roles ───
# Column role detection heuristics (applied to DataFrame schema)
def infer_column_roles(df, override=None):
    cols = df.columns
    roles = {}
    used = set()

    def find_by_keywords(cols, keywords, exclude=None):
        for col in cols:
            if col in used or (exclude and col in exclude):
                continue
            if any(kw in col.lower() for kw in keywords):
                return col
        return None

    # Transaction ID: exact or keyword match, then first unique int column
    if override and 'transaction_id' in override:
        roles['transaction_id'] = override['transaction_id']
        used.add(override['transaction_id'])
    else:
        tid = find_by_keywords(cols, ['id', 'txn'])
        if tid:
            roles['transaction_id'] = tid
            used.add(tid)
        else:
            # Fallback: first column with unique values
            for col in cols:
                if col not in used and df.select(col).distinct().count() == raw_count:
                    roles['transaction_id'] = col
                    used.add(col)
                    break

    # Amount: keyword match, then first numeric with all positive values
    if override and 'amount' in override:
        roles['amount'] = override['amount']
        used.add(override['amount'])
    else:
        amt = find_by_keywords(cols, ['amt', 'amount', 'price', 'total', 'value', 'sum'])
        if amt:
            roles['amount'] = amt
            used.add(amt)
        else:
            for col in cols:
                if col not in used and dict(df.dtypes)[col] in ['double', 'int', 'bigint', 'float']:
                    if df.filter(F.col(col) > 0).count() > raw_count * 0.9:
                        roles['amount'] = col
                        used.add(col)
                        break

    # Timestamp: keyword match
    if override and 'timestamp' in override:
        roles['timestamp'] = override['timestamp']
        used.add(override['timestamp'])
    else:
        ts = find_by_keywords(cols, ['date', 'time', 'dt', 'timestamp'])
        if ts:
            roles['timestamp'] = ts
            used.add(ts)

    # Card number: keyword match
    if override and 'card_number' in override:
        roles['card_number'] = override['card_number']
        used.add(override['card_number'])
    else:
        card = find_by_keywords(cols, ['card', 'pan', 'account'])
        if card:
            roles['card_number'] = card
            used.add(card)

    # Address columns: keyword match
    for canon, keywords in [('address_1', ['addr1', 'address1', 'city', 'state']),
                             ('address_2', ['addr2', 'address2', 'zip', 'postal'])]:
        if override and canon in override:
            roles[canon] = override[canon]
            used.add(override[canon])
        else:
            addr = find_by_keywords(cols, keywords)
            if addr:
                roles[canon] = addr
                used.add(addr)

    # Product code: keyword match
    if override and 'product_code' in override:
        roles['product_code'] = override['product_code']
        used.add(override['product_code'])
    else:
        prod = find_by_keywords(cols, ['product', 'category', 'merchant', 'type'])
        if prod:
            # Verify it's low-cardinality (likely categorical)
            if df.select(prod).distinct().count() < min(100, raw_count * 0.1):
                roles['product_code'] = prod
                used.add(prod)

    return roles

roles = infer_column_roles(df, override_mappings)
print(f"Detected column roles: {json.dumps(roles, indent=2)}")

# ─── Step 4: Normalize columns to canonical names ───
rename_map = {}
for canonical, source in roles.items():
    if source in df.columns and canonical != source:
        rename_map[source] = canonical
if rename_map:
    for old_name, new_name in rename_map.items():
        df = df.withColumnRenamed(old_name, new_name)

# ─── Step 5: Conditional feature engineering ───
# Deduplication
if 'transaction_id' in df.columns:
    df = df.dropDuplicates(['transaction_id'])

# Ensure amount column exists and is positive
if 'amount' in df.columns:
    df = df.withColumn('amount', F.col('amount').cast('double'))
    df = df.filter(F.col('amount') > 0)

# Card masking (conditional)
if 'card_number' in df.columns:
    df = df.withColumn('card_masked',
        F.concat(F.lit('****-****-****-'),
        F.substring(F.col('card_number').cast('string'), -4, 4)))

# Transaction hour + weekend (conditional on timestamp)
if 'timestamp' in df.columns:
    from pyspark.sql.types import IntegerType
    # Try numeric timestamp (seconds like TransactionDT) first
    ts_dtype = dict(df.dtypes)['timestamp']
    if ts_dtype in ['bigint', 'int', 'long']:
        df = df.withColumn('transaction_hour',
            (F.col('timestamp') / 3600 % 24).cast('int'))
        df = df.withColumn('is_weekend',
            ((F.col('timestamp') / 86400 % 7) >= 5).cast('int'))
        df = df.withColumn('month',
            (F.col('timestamp') / 2592000 % 12 + 1).cast('int'))
        df = df.withColumn('day',
            (F.col('timestamp') / 86400 % 30 + 1).cast('int'))
    else:
        # Try parsing as ISO datetime string
        df = df.withColumn('transaction_hour',
            F.hour(F.col('timestamp')).cast('int'))
        df = df.withColumn('is_weekend',
            (F.dayofweek(F.col('timestamp')).isin(1, 7)).cast('int'))
        df = df.withColumn('month', F.month(F.col('timestamp')).cast('int'))
        df = df.withColumn('day', F.dayofmonth(F.col('timestamp')).cast('int'))

# Amount bucket (always computed if amount exists)
if 'amount' in df.columns:
    df = df.withColumn('amount_bucket',
        F.when(F.col('amount') < 50, 'low')
         .when(F.col('amount') < 500, 'medium')
         .otherwise('high'))

# Velocity (conditional on transaction_id + transaction_hour)
if 'transaction_id' in df.columns and 'transaction_hour' in df.columns:
    window_card = Window.partitionBy('transaction_hour')
    df = df.withColumn('txn_velocity',
        F.count('transaction_id').over(window_card))

# Merchant avg + deviation (conditional on product_code + amount)
if 'product_code' in df.columns and 'amount' in df.columns:
    window_merchant = Window.partitionBy('product_code')
    df = df.withColumn('merchant_avg_amount',
        F.avg('amount').over(window_merchant))
    df = df.withColumn('amount_deviation',
        F.abs(F.col('amount') - F.col('merchant_avg_amount')) /
        (F.col('merchant_avg_amount') + F.lit(1e-9)))

# Geo flag (conditional on address columns)
if 'address_1' in df.columns and 'address_2' in df.columns:
    df = df.withColumn('geo_flag',
        (F.col('address_1') != F.col('address_2')).cast('int'))

# ─── Step 6: Partition columns ───
# Default year + synthetic region if not derived from timestamp
if 'year' not in df.columns:
    df = df.withColumn('year', F.lit(2024))
if 'month' not in df.columns:
    if 'transaction_id' in df.columns:
        df = df.withColumn('month',
            (F.col('transaction_id') % 12 + 1).cast('int'))
    else:
        df = df.withColumn('month', F.lit(1))
if 'day' not in df.columns:
    if 'transaction_id' in df.columns:
        df = df.withColumn('day',
            (F.col('transaction_id') % 30 + 1).cast('int'))
    else:
        df = df.withColumn('day', F.lit(1))
if 'region' not in df.columns:
    regions = ['ap-south-1', 'us-east-1', 'eu-west-1']
    region_udf = F.udf(lambda x: regions[x % 3], StringType())
    if 'transaction_id' in df.columns:
        df = df.withColumn('region', region_udf(F.col('transaction_id') % 3))
    else:
        df = df.withColumn('region', F.lit('ap-south-1'))

# Drop nulls from essential columns
essential = [c for c in ['transaction_id', 'amount'] if c in df.columns]
if essential:
    df = df.dropna(subset=essential)
df = df.filter(F.col('region').isNotNull() & F.col('month').isNotNull() & F.col('day').isNotNull())

clean_count = df.count()
print(f"Clean records after ETL: {clean_count:,}")

if clean_count == 0:
    print("WARNING: No records after ETL. Skipping write.")
else:
    # Write Parquet data
    df.write \
      .mode('overwrite') \
      .partitionBy('year', 'month', 'region') \
      .parquet(f"s3://{clean_bucket}/clean/")

    # Write schema metadata for downstream consumers (anomaly Lambda)
    schema_info = {
        'source_file': data_path.split('/')[-1],
        'source_format': file_ext,
        'column_roles': {k: v for k, v in roles.items()},
        'renamed_columns': rename_map,
        'detected_features': [c for c in ['transaction_hour', 'is_weekend', 'amount_bucket',
                                            'txn_velocity', 'merchant_avg_amount',
                                            'amount_deviation', 'geo_flag', 'card_masked']
                              if c in df.columns],
        'partition_columns': ['year', 'month', 'region'],
        'record_count': clean_count
    }
    sc.parallelize([json.dumps(schema_info)]).saveAsTextFile(
        f"s3://{clean_bucket}/clean/_schema.json"
    )

print("ETL job complete.")
job.commit()
```

### Shared Auto-Detection Module

```python
# scripts/schema_utils.py
"""Shared column role detection logic for Glue ETL and Lambda.

This module provides the Python (pandas) version of the column role
detection heuristics, used by validate_data.py and anomaly_lambda.py.
The PySpark version is inline in glue_etl_job.py due to Glue's
import limitations.
"""

import re

AMOUNT_KEYWORDS = ['amt', 'amount', 'price', 'total', 'value', 'sum']
TXN_ID_KEYWORDS = ['id', 'txn', 'trans']
TIMESTAMP_KEYWORDS = ['date', 'time', 'dt', 'timestamp']
CARD_KEYWORDS = ['card', 'pan', 'account']
ADDRESS_KEYWORDS = {
    'address_1': ['addr1', 'address1', 'city', 'state'],
    'address_2': ['addr2', 'address2', 'zip', 'postal']
}
PRODUCT_KEYWORDS = ['product', 'category', 'merchant', 'type']


def detect_format(filepath):
    """Detect file format from extension."""
    ext = filepath.rsplit('.', 1)[-1].lower()
    if ext == 'csv':
        return 'csv'
    elif ext in ('parquet', 'pq'):
        return 'parquet'
    elif ext == 'json':
        return 'json'
    raise ValueError(f"Unsupported format: {ext}")


def _find_by_keywords(columns, keywords, used):
    """Find first column matching any keyword."""
    for col in columns:
        if col in used:
            continue
        if any(kw in col.lower() for kw in keywords):
            return col
    return None


def infer_column_roles(df, override=None):
    """Infer canonical column roles from a pandas DataFrame.

    Args:
        df: pandas DataFrame
        override: dict mapping canonical names to source column names

    Returns:
        dict mapping canonical role names to source column names
    """
    override = override or {}
    cols = list(df.columns)
    roles = {}
    used = set()

    # Transaction ID
    if 'transaction_id' in override:
        roles['transaction_id'] = override['transaction_id']
        used.add(override['transaction_id'])
    else:
        tid = _find_by_keywords(cols, TXN_ID_KEYWORDS, used)
        if tid:
            roles['transaction_id'] = tid
            used.add(tid)
        else:
            # Fallback: first column with all unique values
            for col in cols:
                if col not in used and df[col].is_unique:
                    roles['transaction_id'] = col
                    used.add(col)
                    break

    # Amount
    if 'amount' in override:
        roles['amount'] = override['amount']
        used.add(override['amount'])
    else:
        amt = _find_by_keywords(cols, AMOUNT_KEYWORDS, used)
        if amt:
            roles['amount'] = amt
            used.add(amt)
        else:
            # Fallback: first numeric column with >90% positive values
            for col in cols:
                if col not in used and df[col].dtype in ['float64', 'int64']:
                    if (df[col] > 0).sum() > len(df) * 0.9:
                        roles['amount'] = col
                        used.add(col)
                        break

    # Timestamp
    if 'timestamp' in override:
        roles['timestamp'] = override['timestamp']
        used.add(override['timestamp'])
    else:
        ts = _find_by_keywords(cols, TIMESTAMP_KEYWORDS, used)
        if ts:
            roles['timestamp'] = ts
            used.add(ts)

    # Card number
    if 'card_number' in override:
        roles['card_number'] = override['card_number']
        used.add(override['card_number'])
    else:
        card = _find_by_keywords(cols, CARD_KEYWORDS, used)
        if card:
            roles['card_number'] = card
            used.add(card)

    # Address columns
    for canon, keywords in ADDRESS_KEYWORDS.items():
        if canon in override:
            roles[canon] = override[canon]
            used.add(override[canon])
        else:
            addr = _find_by_keywords(cols, keywords, used)
            if addr:
                roles[canon] = addr
                used.add(addr)

    # Product code
    if 'product_code' in override:
        roles['product_code'] = override['product_code']
        used.add(override['product_code'])
    else:
        prod = _find_by_keywords(cols, PRODUCT_KEYWORDS, used)
        if prod and df[prod].nunique() < min(100, len(df) * 0.1):
            roles['product_code'] = prod
            used.add(prod)

    return roles


def validate_minimum_columns(roles):
    """Ensure at least transaction_id and amount are detected."""
    missing = []
    if 'transaction_id' not in roles:
        missing.append('transaction_id (unique ID column)')
    if 'amount' not in roles:
        missing.append('amount (positive numeric column)')
    if missing:
        raise ValueError(
            f"Could not detect required columns: {missing}. "
            f"Detected: {roles}. Pass --OVERRIDE_MAPPINGS to specify manually."
        )
    return True
```

### Deploy & Run

```bash
# Upload ETL script + schema_utils to S3
aws s3 cp scripts/glue_etl_job.py s3://payflow-glue-scripts-dev-104573823385/
aws s3 cp scripts/schema_utils.py s3://payflow-glue-scripts-dev-104573823385/

# Trigger Glue job (no filename hardcoded — auto-discovers files in raw bucket)
aws glue start-job-run --job-name payflow-etl-job --region ap-south-1

# With column override (optional):
aws glue start-job-run --job-name payflow-etl-job --region ap-south-1 \
  --arguments '{"--SOURCE_CONFIG": "{\"transaction_id\": \"my_id\", \"amount\": \"my_value\"}"}'

# Wait for completion (~5 mins), then run crawlers
aws glue start-crawler --name payflow-clean-crawler --region ap-south-1
# After clean crawler completes:
aws glue start-crawler --name payflow-scored-crawler --region ap-south-1
```

**End of Day 2 Checklist**
- [ ] Glue ETL job completes successfully (~5 min)
- [ ] ETL accepts CSV, Parquet, and JSON input formats
- [ ] Column roles auto-detected (or overridden via `--SOURCE_CONFIG`)
- [ ] `_schema.json` written to clean bucket with detected column mappings
- [ ] Parquet files visible in `clean/` prefix in clean S3 bucket
- [ ] Partitions: year / month / region
- [ ] Conditional feature engineering — only computes features if source columns are detected
- [ ] Glue Crawlers populated `payflow_db` in Data Catalog
- [ ] All detected feature columns present in output schema

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

### Source-Agnostic Lambda Function Code

> **Key Changes from V1:** The Lambda now reads `_schema.json` from the clean bucket to determine available columns, dynamically builds the feature matrix based on what's detected, and writes `_summary.json` to the scored bucket for the frontend results API.

```python
# scripts/anomaly_lambda.py
import boto3
import io
import os
import json
import traceback
from datetime import datetime

import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

s3  = boto3.client('s3')
sns = boto3.client('sns', region_name=os.environ['REGION'])  # NOT AWS_REGION

CLEAN_BUCKET  = os.environ['CLEAN_BUCKET']
SCORED_BUCKET = os.environ['SCORED_BUCKET']
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']


def _read_schema(bucket):
    """Read _schema.json from the clean bucket to determine available columns."""
    try:
        # _schema.json may be written as a single file or by Spark as a directory
        resp = s3.get_object(Bucket=bucket, Key='clean/_schema.json/part-00000')
        return json.loads(resp['Body'].read().decode('utf-8').strip())
    except s3.exceptions.NoSuchKey:
        pass
    except Exception:
        pass
    # Fallback: try without part prefix
    try:
        resp = s3.get_object(Bucket=bucket, Key='clean/_schema.json')
        return json.loads(resp['Body'].read().decode('utf-8'))
    except Exception:
        return None


def _build_column_list(schema):
    """Build the list of columns to project from Parquet files based on schema."""
    # Start with detected source columns (original names)
    columns = set()
    roles = schema.get('column_roles', {})
    for canonical, source in roles.items():
        columns.add(source)

    # Add engineered feature columns (written by Glue ETL)
    features = schema.get('detected_features', [])
    columns.update(features)

    # Add partition columns (extracted from S3 keys, but useful as fallback)
    columns.add('year')
    columns.add('month')
    columns.add('region')
    columns.add('day')

    return list(columns)


def _read_parquet_from_bucket(bucket, columns=None):
    """Read all Parquet files from the bucket, optionally projecting specific columns."""
    paginator = s3.get_paginator('list_objects_v2')
    dfs = []
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if key.endswith('.parquet'):
                resp = s3.get_object(Bucket=bucket, Key=key)
                body_bytes = resp['Body'].read()  # Read full body (not stream)
                read_kwargs = {}
                if columns:
                    available_cols = [c for c in columns if c != 'year' and c != 'month' and c != 'region']
                    read_kwargs['columns'] = available_cols
                chunk = pd.read_parquet(io.BytesIO(body_bytes), **read_kwargs)
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


def _build_features(df, schema):
    """Dynamically build feature matrix based on available columns detected by ETL."""
    features = pd.DataFrame()
    available = set(df.columns)

    # txn_velocity — if available from ETL
    if 'txn_velocity' in available:
        features['txn_velocity'] = df['txn_velocity'].fillna(0).astype(float)

    # amount_z_score — needs amount + merchant_avg_amount
    if 'amount' in available and 'merchant_avg_amount' in available:
        features['amount_z_score'] = (
            (df['amount'].astype(float) - df['merchant_avg_amount'].astype(float)) /
            (df['merchant_avg_amount'].astype(float).std() + 1e-9)
        )

    # geo_jump_score — if available from ETL
    if 'geo_flag' in available:
        features['geo_jump_score'] = df['geo_flag'].fillna(0).astype(float)

    # hour_risk_score — if transaction_hour available from ETL
    if 'transaction_hour' in available:
        features['hour_risk_score'] = df['transaction_hour'].apply(
            lambda h: 1.5 if (pd.notna(h) and (h >= 23 or h <= 4)) else 1.0
        )

    # amount_bucket_enc — needs amount_bucket
    if 'amount_bucket' in available:
        features['amount_bucket_enc'] = df['amount_bucket'].map(
            {'low': 0, 'medium': 1, 'high': 2}
        ).fillna(0).astype(float)

    # is_weekend — if available from ETL
    if 'is_weekend' in available:
        features['is_weekend'] = df['is_weekend'].fillna(0).astype(float)

    # Fallback: if very few features, create basic ones from amount
    if len(features.columns) < 2 and 'amount' in available:
        features['amount_z_fallback'] = (
            (df['amount'].astype(float) - df['amount'].astype(float).mean()) /
            (df['amount'].astype(float).std() + 1e-9)
        )

    return features


def lambda_handler(event, context):
    try:
        print("Reading schema from clean bucket...")
        schema = _read_schema(CLEAN_BUCKET)

        print("Reading clean data from S3...")
        if schema:
            columns = _build_column_list(schema)
            df = _read_parquet_from_bucket(CLEAN_BUCKET, columns=columns)
        else:
            # Fallback: read all columns
            df = _read_parquet_from_bucket(CLEAN_BUCKET)

        print(f"Loaded {len(df):,} records")

        # Build dynamic feature matrix
        features = _build_features(df, schema or {})

        if features.empty or len(features.columns) == 0:
            raise ValueError("No features could be constructed from the available data. "
                           "Ensure the source data has at least an amount column.")

        print(f"Using {len(features.columns)} features: {list(features.columns)}")

        # Fill any remaining NaN with 0
        features = features.fillna(0)

        print("Training Isolation Forest model...")
        scaler = StandardScaler()
        X = scaler.fit_transform(features)

        model = IsolationForest(
            n_estimators=100,
            contamination=0.02,
            random_state=42,
            n_jobs=1
        )
        model.fit(X)

        raw_scores = model.decision_function(X)

        df['anomaly_score'] = (
            100 * (1 - (raw_scores - raw_scores.min()) /
            (raw_scores.max() - raw_scores.min()))
        ).round(2)

        df['is_anomaly'] = (model.predict(X) == -1).astype(int)

        print(f"Anomalies detected: {df['is_anomaly'].sum():,}")

        # Build scored output columns (available columns only)
        scored_columns = ['TransactionID', 'amount', 'anomaly_score', 'is_anomaly',
                          'geo_flag', 'transaction_hour', 'amount_bucket',
                          'txn_velocity', 'ProductCD', 'year', 'month', 'day', 'region']
        available_scored = [c for c in scored_columns if c in df.columns]
        # Always include core columns
        for core_col in ['anomaly_score', 'is_anomaly', 'year', 'month', 'region']:
            if core_col not in available_scored and core_col in df.columns:
                available_scored.append(core_col)
        df_scored = df[available_scored].copy()

        del df, features, X, raw_scores, model, scaler
        print("Garbage collected intermediate data.")

        # Write scored data partitioned to S3
        print("Writing scored data to S3 in partitions...")
        for (year_val, month_val, region_val), group in df_scored.groupby(['year', 'month', 'region']):
            partition_key = f"scored/year={int(year_val)}/month={int(month_val)}/region={region_val}/scored.parquet"
            buffer = io.BytesIO()
            group.drop(columns=['year', 'month', 'region']).to_parquet(buffer, index=False)
            buffer.seek(0)
            s3.put_object(
                Bucket=SCORED_BUCKET,
                Key=partition_key,
                Body=buffer.getvalue()
            )
        print(f"Wrote {len(df_scored):,} scored records across partitions.")

        top_anomalies = df_scored[df_scored['is_anomaly'] == 1].nlargest(1000, 'anomaly_score')
        top_cols = [c for c in ['TransactionID', 'amount', 'anomaly_score',
                                  'geo_flag', 'transaction_hour', 'amount_bucket',
                                  'txn_velocity', 'ProductCD'] if c in top_anomalies.columns]
        top_anomalies = top_anomalies[top_cols]

        csv_buffer = io.StringIO()
        top_anomalies.to_csv(csv_buffer, index=False)
        s3.put_object(
            Bucket=SCORED_BUCKET,
            Key='top_anomalies.csv',
            Body=csv_buffer.getvalue()
        )

        total   = len(df_scored)
        flagged = int(df_scored['is_anomaly'].sum())

        # Write _summary.json for frontend results API
        source_file = schema.get('source_file', 'unknown') if schema else 'unknown'
        features_used = list(features.columns) if 'features' in dir() else []

        summary = {
            'total_scored': total,
            'anomalies_detected': flagged,
            'anomaly_rate_pct': round(flagged/total*100, 2) if total > 0 else 0,
            'source_file': source_file,
            'features_used': list(features.columns) if not features.empty else [],
            'completed_at': datetime.utcnow().isoformat() + 'Z'
        }
        s3.put_object(
            Bucket=SCORED_BUCKET,
            Key='_summary.json',
            Body=json.dumps(summary)
        )

        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject='[PayFlow] Anomaly Detection Complete',
            Message=f"""
PayFlow -- Anomaly Detection Report
===================================
Source file       : {source_file}
Features used     : {', '.join(features_used)}
Records scored    : {total:,}
Anomalies flagged : {flagged:,}
Anomaly rate      : {flagged/total*100:.2f}%

Full results  : s3://{SCORED_BUCKET}/scored/
Top anomalies : s3://{SCORED_BUCKET}/top_anomalies.csv
            """
        )

        return {
            'statusCode': 200,
            'body': json.dumps({
                'total_scored'       : total,
                'anomalies_detected' : flagged,
                'anomaly_rate_pct'   : round(flagged/total*100, 2),
                'features_used'      : list(features.columns) if not features.empty else [],
                'source_file'        : source_file
            })
        }

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

# Upload data (via CLI — or use the web portal)
aws s3 cp my_data.csv s3://payflow-raw-transactions-dev-104573823385/

# Option A: S3 upload triggers EventBridge → glue_trigger Lambda → Glue ETL job
# (This also works when uploading via the web portal — same EventBridge rule)
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
# {"statusCode":200,"body":"{\"total_scored\":590540,\"anomalies_detected\":11811,\"anomaly_rate_pct\":2.0,\"features_used\":[\"txn_velocity\",\"amount_z_score\",\"geo_jump_score\",\"hour_risk_score\",\"amount_bucket_enc\",\"is_weekend\"],\"source_file\":\"train_transaction.csv\"}"}
```

**End of Day 4 Checklist**
- [ ] Lambda container image built with `--platform linux/amd64 --provenance=false`
- [ ] Lambda deployed via Terraform with DLQ + SNS configured
- [ ] Lambda reads `_schema.json` from clean bucket to determine available columns
- [ ] Feature matrix built dynamically from available data (not hardcoded columns)
- [ ] Lambda reads ALL partitioned Parquet files via S3 paginator (not just one)
- [ ] Lambda extracts partition columns from S3 key paths (not Parquet column projection)
- [ ] Lambda uses `REGION` env var (not `AWS_REGION` — which is reserved)
- [ ] Lambda reads S3 body bytes into BytesIO (not streaming Body)
- [ ] Lambda writes scored data partitioned by year/month/region
- [ ] Lambda writes `_summary.json` to scored bucket for frontend results API
- [ ] `anomaly_score` and `is_anomaly` columns in scored output
- [ ] `top_anomalies.csv` exported to S3
- [ ] SNS alert email received with source file and features used
- [ ] EventBridge Rule 1: S3 upload → glue_trigger Lambda (working)
- [ ] EventBridge Rule 2: Glue success → crawler_trigger Lambda (working)
- [ ] Scored table visible in Athena Data Catalog
- [ ] IAM policies are scoped (least-privilege, no S3FullAccess)
- [ ] Lambda container cold start tested (expect 45-60s on first invoke)
- [ ] Source-agnostic: works with any dataset that has at least ID + amount columns

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
- Source-agnostic ETL explanation (auto-detection, supported formats, override mechanism)
- Frontend portal setup (S3 + CloudFront)
- API Gateway endpoints
- Sample Athena query output (screenshots)
- QuickSight dashboard link
- Anomaly detection results summary (590,540 scored, 11,811 anomalies, 2.00% rate)

---

## Day 6 — Frontend Upload Portal + API Gateway

### Goal: Web UI for uploading any data source, monitoring pipeline status, and viewing anomaly detection results

---

### Frontend Architecture

```
Browser (HTML/JS)
    │
    ├── POST /upload-url ──► API Gateway ──► Presigned URL Lambda ──► Presigned S3 URL
    │                                                                          │
    │   ◄── Returns presigned URL ◄────────────────────────────────────────────┘
    │
    ├── PUT file directly to S3 (raw bucket, via presigned URL)
    │       │
    │       └──► S3 ObjectCreated ──► EventBridge ──► Glue Trigger Lambda ──► Glue ETL
    │                                                                          │
    │   GET /pipeline-status ──► API Gateway ──► Status Lambda ──► Checks Glue/Crawler/S3
    │       ◄── Returns stage, status, timestamps
    │
    └── GET /results ──► API Gateway ──► Results Lambda ──► Reads _summary.json + top_anomalies.csv
            ◄── Returns anomaly stats + top suspicious transactions
```

> **No authentication on API endpoints** — open for demo use. Add API key authentication for production.

> **Auto-trigger pipeline**: The existing EventBridge rule on S3 ObjectCreated automatically triggers the Glue ETL job when a file is uploaded via presigned URL. No new trigger mechanism is needed.

---

### Frontend Files

#### `frontend/index.html`

Single page with 3 panels:

| Panel | Content |
|-------|---------|
| **Upload** | Drag-and-drop zone, file picker (CSV/Parquet/JSON), progress bar, detected format badge |
| **Pipeline Status** | Step tracker showing: Upload → Glue ETL → Crawlers → Anomaly Detection. Each step shows `pending`/`running`/`complete`/`failed` with timestamps. Auto-polls every 10s. |
| **Results** | Summary cards (records scored, anomalies detected, anomaly rate %, source file, features used). Table of top 100 anomalies. Download button for full results CSV. |

```html
<!-- frontend/index.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PayFlow — Anomaly Detection Pipeline</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <header>
        <h1>PayFlow</h1>
        <p>Payment Transaction Anomaly Detection Pipeline</p>
    </header>

    <main>
        <!-- Upload Panel -->
        <section id="upload-panel" class="panel">
            <h2>Upload Data</h2>
            <div id="drop-zone" class="drop-zone">
                <p>Drag & drop your file here</p>
                <p class="formats">Supported: CSV, Parquet, JSON</p>
                <input type="file" id="file-input" accept=".csv,.parquet,.json">
                <button id="upload-btn" disabled>Upload</button>
            </div>
            <div id="upload-progress" class="hidden">
                <div class="progress-bar"><div id="progress-fill"></div></div>
                <span id="progress-text">0%</span>
            </div>
            <div id="upload-status" class="hidden"></div>
        </section>

        <!-- Pipeline Status Panel -->
        <section id="status-panel" class="panel">
            <h2>Pipeline Status</h2>
            <div class="steps">
                <div class="step" id="step-upload">
                    <div class="step-icon">⬆</div>
                    <div class="step-label">Upload</div>
                    <div class="step-status">pending</div>
                </div>
                <div class="step" id="step-etl">
                    <div class="step-icon">⚙</div>
                    <div class="step-label">Glue ETL</div>
                    <div class="step-status">pending</div>
                </div>
                <div class="step" id="step-crawler">
                    <div class="step-icon">📋</div>
                    <div class="step-label">Crawlers</div>
                    <div class="step-status">pending</div>
                </div>
                <div class="step" id="step-anomaly">
                    <div class="step-icon">🔍</div>
                    <div class="step-label">Anomaly Detection</div>
                    <div class="step-status">pending</div>
                </div>
            </div>
            <button id="refresh-status-btn">Refresh Status</button>
        </section>

        <!-- Results Panel -->
        <section id="results-panel" class="panel hidden">
            <h2>Results</h2>
            <div class="summary-cards">
                <div class="card"><span id="res-total" class="big-number">-</span><label>Records Scored</label></div>
                <div class="card"><span id="res-anomalies" class="big-number">-</span><label>Anomalies Detected</label></div>
                <div class="card"><span id="res-rate" class="big-number">-</span><label>Anomaly Rate</label></div>
                <div class="card"><span id="res-source" class="big-number">-</span><label>Source File</label></div>
            </div>
            <h3>Top Anomalies</h3>
            <div id="anomalies-table-container">
                <table id="anomalies-table">
                    <thead><tr id="anomalies-header"></tr></thead>
                    <tbody id="anomalies-body"></tbody>
                </table>
            </div>
            <button id="download-csv-btn">Download Full CSV</button>
        </section>
    </main>

    <script src="app.js"></script>
</body>
</html>
```

#### `frontend/styles.css`

```css
/* frontend/styles.css */
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #0d1117; color: #e6edf3; padding: 2rem; max-width: 900px; margin: 0 auto; }
header { text-align: center; margin-bottom: 2rem; }
header h1 { font-size: 2rem; color: #58a6ff; }
header p { color: #8b949e; margin-top: 0.25rem; }

.panel { background: #161b22; border: 1px solid #30363d; border-radius: 8px;
         padding: 1.5rem; margin-bottom: 1.5rem; }
.panel h2 { font-size: 1.25rem; margin-bottom: 1rem; color: #58a6ff; }
.panel h3 { font-size: 1rem; margin: 1rem 0 0.5rem; color: #c9d1d9; }

.hidden { display: none !important; }

/* Drop Zone */
.drop-zone { border: 2px dashed #30363d; border-radius: 8px; padding: 2rem;
             text-align: center; cursor: pointer; transition: border-color 0.2s; }
.drop-zone:hover, .drop-zone.drag-over { border-color: #58a6ff; background: #1a2332; }
.drop-zone p { color: #8b949e; margin: 0.5rem 0; }
.drop-zone .formats { font-size: 0.85rem; color: #6e7681; }
.drop-zone input[type="file"] { display: none; }
.drop-zone button { margin-top: 1rem; padding: 0.5rem 1.5rem; background: #238636;
                    color: white; border: none; border-radius: 4px; cursor: pointer;
                    font-size: 0.9rem; }
.drop-zone button:disabled { background: #30363d; color: #6e7681; cursor: not-allowed; }

/* Progress Bar */
.progress-bar { width: 100%; height: 8px; background: #21262d; border-radius: 4px;
                overflow: hidden; margin-top: 1rem; }
.progress-bar > div { height: 100%; background: #58a6ff; transition: width 0.3s; }

/* Steps */
.steps { display: flex; justify-content: space-between; margin: 1rem 0; }
.step { text-align: center; flex: 1; }
.step-icon { font-size: 1.5rem; }
.step-label { font-size: 0.8rem; color: #8b949e; margin-top: 0.25rem; }
.step-status { font-size: 0.75rem; margin-top: 0.25rem; padding: 2px 8px;
               border-radius: 10px; display: inline-block; }
.step-status.pending { background: #21262d; color: #6e7681; }
.step-status.running { background: #1f3a5f; color: #58a6ff; }
.step-status.complete { background: #1b3f24; color: #3fb950; }
.step-status.failed { background: #3d1219; color: #f85149; }

#refresh-status-btn { padding: 0.4rem 1rem; background: #21262d; color: #c9d1d9;
    border: 1px solid #30363d; border-radius: 4px; cursor: pointer; margin-top: 0.5rem; }

/* Summary Cards */
.summary-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1rem; }
.card { background: #21262d; border-radius: 8px; padding: 1rem; text-align: center; }
.big-number { display: block; font-size: 1.75rem; font-weight: bold; color: #58a6ff; }
.card label { display: block; font-size: 0.75rem; color: #8b949e; margin-top: 0.25rem; }

/* Anomalies Table */
#anomalies-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
#anomalies-table th { background: #21262d; color: #8b949e; padding: 0.5rem;
                      text-align: left; border-bottom: 1px solid #30363d; }
#anomalies-table td { padding: 0.5rem; border-bottom: 1px solid #21262d; }
#anomalies-table tr:hover td { background: #1a2332; }

#download-csv-btn { padding: 0.5rem 1.5rem; background: #238636; color: white;
    border: none; border-radius: 4px; cursor: pointer; margin-top: 1rem; font-size: 0.9rem; }

#upload-status { margin-top: 1rem; padding: 0.75rem; border-radius: 4px; }
#upload-status.success { background: #1b3f24; color: #3fb950; }
#upload-status.error { background: #3d1219; color: #f85149; }
```

#### `frontend/app.js`

```javascript
// frontend/app.js
const API_BASE = ''; // Set to API Gateway URL after deployment, e.g. 'https://xxxxx.execute-api.ap-south-1.amazonaws.com/prod'

const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const uploadBtn = document.getElementById('upload-btn');
const uploadProgress = document.getElementById('upload-progress');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const uploadStatus = document.getElementById('upload-status');
const refreshBtn = document.getElementById('refresh-status-btn');
const resultsPanel = document.getElementById('results-panel');

const ALLOWED_EXTENSIONS = ['.csv', '.parquet', '.json'];
let selectedFile = null;
let pollInterval = null;

// Upload: click drop zone to open file picker
dropZone.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        selectFile(e.target.files[0]);
    }
});

// Drag and drop
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    if (e.dataTransfer.files.length > 0) selectFile(e.dataTransfer.files[0]);
});

function selectFile(file) {
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
        showUploadStatus(`Unsupported format: ${ext}. Please use CSV, Parquet, or JSON.`, 'error');
        return;
    }
    selectedFile = file;
    uploadBtn.disabled = false;
    dropZone.querySelector('p').textContent = file.name;
}

// Upload: get presigned URL then PUT file
uploadBtn.addEventListener('click', async () => {
    if (!selectedFile) return;
    uploadBtn.disabled = true;
    uploadProgress.classList.remove('hidden');

    try {
        // Step 1: Get presigned URL
        const presignRes = await fetch(`${API_BASE}/upload-url`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: selectedFile.name,
                content_type: selectedFile.type || 'application/octet-stream'
            })
        });
        if (!presignRes.ok) throw new Error('Failed to get upload URL');
        const { upload_url, file_key } = await presignRes.json();

        // Step 2: Upload file directly to S3
        await uploadFileToS3(selectedFile, upload_url);

        showUploadStatus(`File uploaded successfully: ${selectedFile.name}`, 'success');
        setStepStatus('step-upload', 'complete');

        // Step 3: Start polling pipeline status
        startPolling();
    } catch (err) {
        showUploadStatus(`Upload failed: ${err.message}`, 'error');
        uploadBtn.disabled = false;
    }
});

function uploadFileToS3(file, presignedUrl) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('PUT', presignedUrl);
        xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream');

        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
                const pct = Math.round((e.loaded / e.total) * 100);
                progressFill.style.width = pct + '%';
                progressText.textContent = pct + '%';
            }
        };

        xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) resolve();
            else reject(new Error(`S3 upload failed: ${xhr.status}`));
        };
        xhr.onerror = () => reject(new Error('S3 upload network error'));
        xhr.send(file);
    });
}

// Pipeline Status Polling
refreshBtn.addEventListener('click', fetchPipelineStatus);

function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    fetchPipelineStatus();
    pollInterval = setInterval(fetchPipelineStatus, 10000);
}

async function fetchPipelineStatus() {
    try {
        const res = await fetch(`${API_BASE}/pipeline-status`);
        if (!res.ok) throw new Error('Status check failed');
        const data = await res.json();

        for (const stage of data.stages) {
            const stepId = {
                'upload': 'step-upload',
                'glue_etl': 'step-etl',
                'crawlers': 'step-crawler',
                'anomaly_detection': 'step-anomaly'
            }[stage.name];
            if (stepId) setStepStatus(stepId, stage.status);
        }

        // If anomaly detection is complete, fetch results
        const anomalyStage = data.stages.find(s => s.name === 'anomaly_detection');
        if (anomalyStage && anomalyStage.status === 'complete') {
            clearInterval(pollInterval);
            fetchResults();
        }
    } catch (err) {
        console.error('Status poll error:', err);
    }
}

function setStepStatus(stepId, status) {
    const el = document.getElementById(stepId);
    if (!el) return;
    const statusEl = el.querySelector('.step-status');
    statusEl.textContent = status;
    statusEl.className = 'step-status ' + status;
}

// Fetch Results
async function fetchResults() {
    try {
        const res = await fetch(`${API_BASE}/results`);
        if (!res.ok) throw new Error('Results fetch failed');
        const data = await res.json();

        resultsPanel.classList.remove('hidden');
        document.getElementById('res-total').textContent = data.summary.total_scored.toLocaleString();
        document.getElementById('res-anomalies').textContent = data.summary.anomalies_detected.toLocaleString();
        document.getElementById('res-rate').textContent = data.summary.anomaly_rate_pct + '%';
        document.getElementById('res-source').textContent = data.summary.source_file || '-';

        // Populate anomalies table
        if (data.top_anomalies && data.top_anomalies.length > 0) {
            const headers = Object.keys(data.top_anomalies[0]);
            const headerRow = document.getElementById('anomalies-header');
            const tbody = document.getElementById('anomalies-body');
            headerRow.innerHTML = headers.map(h => `<th>${h}</th>`).join('');
            tbody.innerHTML = data.top_anomalies.slice(0, 100).map(row =>
                '<tr>' + headers.map(h => `<td>${row[h] != null ? row[h] : '-'}</td>`).join('') + '</tr>'
            ).join('');
        }
    } catch (err) {
        console.error('Results fetch error:', err);
    }
}

// Download CSV button
document.getElementById('download-csv-btn').addEventListener('click', () => {
    // Redirect to S3 presigned URL for top_anomalies.csv or API endpoint
    window.open(`${API_BASE}/results?download=true`, '_blank');
});

function showUploadStatus(msg, type) {
    uploadStatus.classList.remove('hidden', 'success', 'error');
    uploadStatus.classList.add(type);
    uploadStatus.textContent = msg;
}
```

---

### API Lambda Functions

#### `scripts/presigned_url_lambda.py`

```python
import boto3
import os
import json

s3 = boto3.client('s3')
RAW_BUCKET = os.environ['RAW_BUCKET']

ALLOWED_EXTENSIONS = {'.csv': 'text/csv', '.parquet': 'application/octet-stream', '.json': 'application/json'}

def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        filename = body.get('filename', '')
        content_type = body.get('content_type', 'application/octet-stream')

        ext = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in ALLOWED_EXTENSIONS:
            return {
                'statusCode': 400,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': f'Unsupported file type: {ext}. Use CSV, Parquet, or JSON.'})
            }

        presigned_url = s3.generate_presigned_url(
            'put_object',
            Params={'Bucket': RAW_BUCKET, 'Key': filename, 'ContentType': content_type},
            ExpiresIn=300  # 5 minutes
        )

        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'upload_url': presigned_url, 'file_key': filename})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)})
        }
```

#### `scripts/pipeline_status_lambda.py`

```python
import boto3
import os
import json

glue = boto3.client('glue', region_name=os.environ.get('REGION', 'ap-south-1'))
s3 = boto3.client('s3', region_name=os.environ.get('REGION', 'ap-south-1'))

PROJECT_NAME = os.environ.get('PROJECT_NAME', 'payflow')
SCORED_BUCKET = os.environ['SCORED_BUCKET']
RAW_BUCKET = os.environ.get('RAW_BUCKET', '')

def lambda_handler(event, context):
    stages = []

    # Stage 1: Upload - check if raw bucket has any files
    upload_status = 'pending'
    try:
        raw_objects = s3.list_objects_v2(Bucket=RAW_BUCKET, MaxKeys=1)
        if raw_objects.get('KeyCount', 0) > 0:
            upload_status = 'complete'
    except Exception:
        pass
    stages.append({'name': 'upload', 'status': upload_status})

    # Stage 2: Glue ETL - check latest job run
    etl_status = 'pending'
    try:
        runs = glue.get_job_runs(JobName=f'{PROJECT_NAME}-etl-job', MaxResults=1)
        if runs['JobRuns']:
            run = runs['JobRuns'][0]
            state = run['JobRunState']
            if state == 'SUCCEEDED':
                etl_status = 'complete'
            elif state in ('RUNNING', 'STARTING'):
                etl_status = 'running'
            elif state == 'FAILED':
                etl_status = 'failed'
    except Exception:
        pass
    stages.append({'name': 'glue_etl', 'status': etl_status})

    # Stage 3: Crawlers
    crawler_status = 'pending'
    try:
        clean_state = glue.get_crawler(Name=f'{PROJECT_NAME}-clean-crawler')['Crawler']['State']
        if clean_state == 'READY':
            # Check if it has run at least once
            clean_crawler = glue.get_crawler(Name=f'{PROJECT_NAME}-clean-crawler')['Crawler']
            if clean_crawler.get('LastCrawl', {}).get('Status') == 'SUCCEEDED':
                crawler_status = 'complete'
        elif 'RUNNING' in clean_state:
            crawler_status = 'running'
    except Exception:
        pass
    stages.append({'name': 'crawlers', 'status': crawler_status})

    # Stage 4: Anomaly detection - check for _summary.json in scored bucket
    anomaly_status = 'pending'
    try:
        s3.head_object(Bucket=SCORED_BUCKET, Key='_summary.json')
        anomaly_status = 'complete'
    except s3.exceptions.ClientError:
        # Check if scored data exists even without summary
        s3.list_objects_v2(Bucket=SCORED_BUCKET, Prefix='scored/', MaxKeys=1)
        scored_objects = s3.list_objects_v2(Bucket=SCORED_BUCKET, Prefix='scored/', MaxKeys=1)
        if scored_objects.get('KeyCount', 0) > 0:
            anomaly_status = 'running'
    except Exception:
        pass
    stages.append({'name': 'anomaly_detection', 'status': anomaly_status})

    return {
        'statusCode': 200,
        'headers': {'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({'stages': stages})
    }
```

#### `scripts/results_lambda.py`

```python
import boto3
import io
import os
import json
import csv

s3 = boto3.client('s3')
SCORED_BUCKET = os.environ['SCORED_BUCKET']

def lambda_handler(event, context):
    try:
        # Check if this is a download request
        query = event.get('queryStringParameters') or {}
        if query.get('download') == 'true':
            presigned = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': SCORED_BUCKET, 'Key': 'top_anomalies.csv'},
                ExpiresIn=300
            )
            return {
                'statusCode': 302,
                'headers': {'Location': presigned, 'Access-Control-Allow-Origin': '*'}
            }

        # Read _summary.json
        summary = {}
        try:
            resp = s3.get_object(Bucket=SCORED_BUCKET, Key='_summary.json')
            summary = json.loads(resp['Body'].read().decode('utf-8'))
        except Exception:
            summary = {'total_scored': 0, 'anomalies_detected': 0,
                       'anomaly_rate_pct': 0, 'source_file': 'unknown', 'features_used': []}

        # Read top_anomalies.csv
        top_anomalies = []
        try:
            resp = s3.get_object(Bucket=SCORED_BUCKET, Key='top_anomalies.csv')
            csv_text = resp['Body'].read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(csv_text))
            top_anomalies = [row for row in reader][:100]
        except Exception:
            pass

        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'summary': summary, 'top_anomalies': top_anomalies})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)})
        }
```

---

### Terraform — New Modules

#### `terraform/modules/api_gateway/main.tf`

```hcl
# API Gateway REST API with 3 routes + CORS

resource "aws_apigatewayv2_api" "payflow_api" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins     = ["https://${var.frontend_domain}", "http://localhost:8000"]
    allow_methods     = ["GET", "POST", "OPTIONS"]
    allow_headers     = ["Content-Type", "x-api-key"]
    max_age           = 300
  }
}

resource "aws_apigatewayv2_integration" "upload_url" {
  api_id           = aws_apigatewayv2_api.payflow_api.id
  integration_type = "AWS_PROXY"
  integration_uri  = var.presigned_lambda_arn
  integration_method = "POST"
}

resource "aws_apigatewayv2_integration" "pipeline_status" {
  api_id           = aws_apigatewayv2_api.payflow_api.id
  integration_type = "AWS_PROXY"
  integration_uri  = var.status_lambda_arn
  integration_method = "GET"
}

resource "aws_apigatewayv2_integration" "results" {
  api_id           = aws_apigatewayv2_api.payflow_api.id
  integration_type = "AWS_PROXY"
  integration_uri  = var.results_lambda_arn
  integration_method = "GET"
}

resource "aws_apigatewayv2_route" "upload_url" {
  api_id    = aws_apigatewayv2_api.payflow_api.id
  route_key = "POST /upload-url"
  target    = "integrations/${aws_apigatewayv2_integration.upload_url.id}"
}

resource "aws_apigatewayv2_route" "pipeline_status" {
  api_id    = aws_apigatewayv2_api.payflow_api.id
  route_key = "GET /pipeline-status"
  target    = "integrations/${aws_apigatewayv2_integration.pipeline_status.id}"
}

resource "aws_apigatewayv2_route" "results" {
  api_id    = aws_apigatewayv2_api.payflow_api.id
  route_key = "GET /results"
  target    = "integrations/${aws_apigatewayv2_integration.results.id}"
}

resource "aws_apigatewayv2_stage" "prod" {
  api_id      = aws_apigatewayv2_api.payflow_api.id
  name        = "prod"
  auto_deploy = true
}

output "api_url" {
  value = aws_apigatewayv2_stage.prod.invoke_url
}
```

#### `terraform/modules/api_lambdas/main.tf`

```hcl
# 3 API Lambda functions + scoped IAM roles

# ─── Presigned URL Lambda ───
resource "aws_iam_role" "api_lambda_role" {
  name = "${var.project_name}-api-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "api_lambda_basic" {
  role       = aws_iam_role.api_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "presigned_s3" {
  name = "${var.project_name}-presigned-s3-policy"
  role = aws_iam_role.api_lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:PutObject"]
      Resource = ["arn:aws:s3:::${var.raw_bucket}/*"]
    }]
  })
}

data "archive_file" "presigned_lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/presigned_lambda.zip"
  source {
    content  = file("${path.module}/../../scripts/presigned_url_lambda.py")
    filename = "lambda_function.py"
  }
}

resource "aws_lambda_function" "presigned_url" {
  function_name    = "${var.project_name}-presigned-url"
  role             = aws_iam_role.api_lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.presigned_lambda_zip.output_path
  source_code_hash = data.archive_file.presigned_lambda_zip.output_base64sha256
  timeout          = 30
  memory_size      = 128
  environment {
    variables = { RAW_BUCKET = var.raw_bucket }
  }
}

# ─── Pipeline Status Lambda ───
resource "aws_iam_role_policy" "status_glue" {
  name = "${var.project_name}-status-glue-policy"
  role = aws_iam_role.api_lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["glue:GetJobRuns", "glue:GetJobRun", "glue:GetCrawler"]
        Resource = ["*"]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::${var.raw_bucket}",
          "arn:aws:s3:::${var.scored_bucket}"
        ]
      }
    ]
  })
}

data "archive_file" "status_lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/status_lambda.zip"
  source {
    content  = file("${path.module}/../../scripts/pipeline_status_lambda.py")
    filename = "lambda_function.py"
  }
}

resource "aws_lambda_function" "pipeline_status" {
  function_name    = "${var.project_name}-pipeline-status"
  role             = aws_iam_role.api_lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.status_lambda_zip.output_path
  source_code_hash = data.archive_file.status_lambda_zip.output_base64sha256
  timeout          = 30
  memory_size      = 128
  environment {
    variables = {
      PROJECT_NAME   = var.project_name
      SCORED_BUCKET  = var.scored_bucket
      RAW_BUCKET     = var.raw_bucket
      REGION         = var.aws_region
    }
  }
}

# ─── Results Lambda ───
resource "aws_iam_role_policy" "results_s3" {
  name = "${var.project_name}-results-s3-policy"
  role = aws_iam_role.api_lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject"]
      Resource = ["arn:aws:s3:::${var.scored_bucket}/*"]
    }]
  })
}

data "archive_file" "results_lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/results_lambda.zip"
  source {
    content  = file("${path.module}/../../scripts/results_lambda.py")
    filename = "lambda_function.py"
  }
}

resource "aws_lambda_function" "results" {
  function_name    = "${var.project_name}-results"
  role             = aws_iam_role.api_lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.results_lambda_zip.output_path
  source_code_hash = data.archive_file.results_lambda_zip.output_base64sha256
  timeout          = 30
  memory_size      = 128
  environment {
    variables = { SCORED_BUCKET = var.scored_bucket }
  }
}

output "presigned_lambda_arn" { value = aws_lambda_function.presigned_url.arn }
output "status_lambda_arn"   { value = aws_lambda_function.pipeline_status.arn }
output "results_lambda_arn"  { value = aws_lambda_function.results.arn }
```

#### `terraform/modules/frontend/main.tf`

```hcl
# S3 Static Website + CloudFront CDN for frontend

resource "aws_s3_bucket" "frontend" {
  bucket = "${var.project_name}-frontend-${var.env}-${var.account_id}"
  tags   = { Project = var.project_name, Stage = "frontend" }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "frontend_public_read" {
  bucket = aws_s3_bucket.frontend.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = "*"
      Action    = ["s3:GetObject"]
      Resource  = ["arn:aws:s3:::${aws_s3_bucket.frontend.id}/*"]
    }]
  })
}

resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  index_document { suffix = "index.html" }
  error_document { key = "index.html" }
}

resource "aws_cloudfront_distribution" "frontend" {
  origin {
    domain_name = aws_s3_bucket_website_configuration.frontend.website_endpoint
    origin_id   = "frontend"
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  enabled             = true
  default_root_object = "index.html"

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "frontend"
    viewer_protocol_policy = "redirect-to-https"
    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate { cloudfront_default_certificate = true }
}

output "frontend_url" { value = aws_cloudfront_distribution.frontend.domain_name }
output "frontend_bucket" { value = aws_s3_bucket.frontend.id }
```

---

### S3 CORS Configuration for Presigned Uploads

Add CORS rule on the raw bucket to allow browser uploads via presigned URLs:

```hcl
# In terraform/modules/s3/main.tf — add after the existing raw bucket resources:

resource "aws_s3_bucket_cors_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT"]
    allowed_origins = [
      "https://${var.frontend_domain}",
      "http://localhost:8000"
    ]
    expose_headers  = []
    max_age_seconds = 300
  }
}
```

---

### Frontend Deployment

```bash
# Upload frontend files to S3
aws s3 sync frontend/ s3://payflow-frontend-dev-104573823385/ --region ap-south-1

# Invalidate CloudFront cache (if updating)
aws cloudfront create-invalidation --distribution-id <DISTRIBUTION_ID> --paths "/*" --region ap-south-1
```

---

### Updated `scripts/validate_data.py`

```python
# scripts/validate_data.py (source-agnostic)
import os
import sys

def find_data_file():
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    if not os.path.exists(data_dir):
        return None
    for f in os.listdir(data_dir):
        ext = f.rsplit('.', 1)[-1].lower()
        if ext in ('csv', 'parquet', 'json'):
            return os.path.join(data_dir, f)
    return None

def validate():
    data_path = find_data_file()
    if data_path is None:
        print("ERROR: No data file found in data/ folder.")
        print("Place a CSV, Parquet, or JSON file in the data/ folder and re-run.")
        sys.exit(1)

    file_ext = data_path.rsplit('.', 1)[-1].lower()
    print(f"Found data file: {os.path.basename(data_path)} (format: {file_ext})")

    import pandas as pd

    if file_ext == 'csv':
        df = pd.read_csv(data_path)
    elif file_ext == 'parquet':
        df = pd.read_parquet(data_path)
    elif file_ext == 'json':
        df = pd.read_json(data_path)
    else:
        print(f"ERROR: Unsupported format: {file_ext}")
        sys.exit(1)

    print(f"\nRecords  : {len(df):,}")
    print(f"Columns  : {len(df.columns)} total")
    print(f"Nulls    : {df.isnull().sum().sum():,}")

    # Auto-detect column roles
    sys.path.insert(0, os.path.dirname(__file__))
    from schema_utils import infer_column_roles, validate_minimum_columns

    roles = infer_column_roles(df)
    print(f"\nDetected column roles:")
    for canonical, source in roles.items():
        print(f"  {canonical:20s} → {source}")

    # Check minimum requirements
    try:
        validate_minimum_columns(roles)
        print("\n✓ Minimum requirements met (transaction_id + amount)")
    except ValueError as e:
        print(f"\n✗ {e}")
        sys.exit(1)

    # Check optional features
    optional_features = {
        'card_masked': 'card_number' in roles,
        'transaction_hour': 'timestamp' in roles,
        'is_weekend': 'timestamp' in roles,
        'txn_velocity': 'transaction_id' in roles and 'timestamp' in roles,
        'merchant_avg_amount': 'product_code' in roles,
        'amount_deviation': 'product_code' in roles,
        'geo_flag': 'address_1' in roles and 'address_2' in roles
    }
    print(f"\nFeature availability:")
    for feature, available in optional_features.items():
        status = '✓' if available else '✗ (skipped)'
        print(f"  {feature:25s} {status}")

    print()
    print("=" * 50)
    print("VALIDATION PASSED - Dataset is ready for the pipeline")
    print("=" * 50)

if __name__ == '__main__':
    validate()
```

### Updated `scripts/upload_to_s3.py`

```python
# scripts/upload_to_s3.py (supports any file format)
import boto3
import sys
import os

ACCOUNT_ID = boto3.client('sts').get_caller_identity()['Account']
REGION = 'ap-south-1'
PREFIX = 'payflow'
ENV = 'dev'

s3 = boto3.client('s3', region_name=REGION)

def get_bucket_name(suffix):
    return f'{PREFIX}-{suffix}-{ENV}-{ACCOUNT_ID}'

SUPPORTED_FORMATS = {
    '.csv': 'raw-transactions',
    '.parquet': 'raw-transactions',
    '.json': 'raw-transactions',
}

def upload_file(local_path, bucket, key):
    s3.upload_file(local_path, bucket, key)
    print(f'Uploaded s3://{bucket}/{key}')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python upload_to_s3.py <local_file> [s3_suffix]')
        print('Example: python upload_to_s3.py data/my_data.csv')
        print('Example: python upload_to_s3.py data/my_data.csv raw-transactions')
        sys.exit(1)

    local_file = sys.argv[1]
    ext = '.' + local_file.rsplit('.', 1)[-1].lower() if '.' in local_file else ''

    if ext not in SUPPORTED_FORMATS:
        print(f'ERROR: Unsupported file format: {ext}')
        print(f'Supported formats: {", ".join(SUPPORTED_FORMATS.keys())}')
        sys.exit(1)

    bucket_suffix = sys.argv[2] if len(sys.argv) > 2 else SUPPORTED_FORMATS[ext]
    bucket_name = get_bucket_name(bucket_suffix)
    file_name = os.path.basename(local_file)

    upload_file(local_file, bucket_name, file_name)
    print(f'Done! File available at s3://{bucket_name}/{file_name}')
```

---

### End of Day 6 Checklist
- [ ] Frontend HTML/CSS/JS uploaded to S3 website bucket
- [ ] CloudFront distribution serving frontend
- [ ] API Gateway created with 3 routes (no auth, CORS enabled)
- [ ] Presigned URL Lambda generates valid PUT URLs for raw bucket
- [ ] Browser can upload files directly to S3 via presigned URL (CORS working)
- [ ] Status Lambda returns Glue job + crawler + scored data status
- [ ] Results Lambda returns `_summary.json` + top anomalies
- [ ] Drag-and-drop upload works with CSV, Parquet, and JSON files
- [ ] Pipeline status auto-polls every 10 seconds
- [ ] Results panel displays anomaly stats and top suspicious transactions
- [ ] S3 raw bucket CORS allows PUT from frontend origin
- [ ] IAM policies for API Lambdas are scoped (no S3FullAccess)
- [ ] Frontend accessible at CloudFront URL

---

## Full Tech Stack

| Layer | Technology | Cost |
|-------|-----------|------|
| Infrastructure | Terraform | Free |
| Orchestration | EventBridge + Lambda intermediary functions | ~$0.00 (free tier) |
| Storage | Amazon S3 | ~$0.05 |
| Frontend Hosting | S3 Static Website + CloudFront | ~$0.51 |
| ETL | AWS Glue PySpark (2 G.1X workers) | ~$0.30 |
| Cataloging | Glue Crawler + Data Catalog | ~$0.05 |
| Governance | AWS Lake Formation (database-level permissions) | Free |
| Querying | Amazon Athena | ~$0.10 |
| ML | AWS Lambda Container Image + Isolation Forest | ~$0.00 (free tier) |
| Container Registry | Amazon ECR (~2GB image) | ~$0.05 |
| Error Handling | SQS Dead-Letter Queue | ~$0.00 |
| Alerts | Amazon SNS | ~$0.00 |
| API | API Gateway HTTP (3 routes, no auth) | ~$0.01 (free tier) |
| API Compute | 3 Python Lambda functions (zip) | ~$0.00 (free tier) |
| Dashboard | Amazon QuickSight | ~$0.00 (30-day free) |
| CI/CD | GitHub Actions | Free |
| **Total** | **1 full week** | **~$1.13** |

---

## Security Checklist

- [ ] No hardcoded AWS credentials — IAM roles only
- [ ] No hardcoded bucket names or ARNs in Lambda — environment variables (`CLEAN_BUCKET`, `SCORED_BUCKET`, `SNS_TOPIC_ARN`, `REGION`, `RAW_BUCKET`)
- [ ] `AWS_REGION` env var NOT used (reserved by Lambda) — uses `REGION` instead
- [ ] Terraform state encrypted in S3 with DynamoDB locking
- [ ] S3 bucket names include `account_id` suffix for global uniqueness
- [ ] S3 EventBridge notifications explicitly enabled on raw bucket (`eventbridge = true`)
- [ ] S3 CORS on raw bucket allows PUT only from frontend origin (CloudFront + localhost)
- [ ] All IAM roles follow least-privilege principle (scoped S3/SNS/SQS policies, not full access)
- [ ] Lambda role includes `sqs:SendMessage` for DLQ
- [ ] Card numbers masked in ETL — never stored in plain text
- [ ] Lake Formation database-level permissions (not table-level — tables don't exist at deploy time)
- [ ] S3 buckets have versioning enabled + public access blocked (except frontend bucket for static website)
- [ ] Athena workgroup has 1GB scan limit per query (cost protection)
- [ ] Lambda has DLQ configured for failed invocations
- [ ] EventBridge rules use Lambda intermediary functions (Glue/Crawler direct targets return 400)
- [ ] Lambda uses `n_jobs=1` (single vCPU environment)
- [ ] API Gateway has no authentication (open for demo — add API key for production)
- [ ] Presigned URLs have 5-minute expiry
- [ ] API Lambda IAM roles are scoped:
  - Presigned URL Lambda: only `s3:PutObject` on raw bucket
  - Status Lambda: only `glue:GetJobRuns`, `glue:GetCrawler`, `s3:ListBucket` on raw + scored
  - Results Lambda: only `s3:GetObject` on scored bucket
- [ ] Frontend S3 bucket has public read policy (no sensitive data is hosted)
- [ ] CloudFront uses HTTPS for frontend distribution
- [ ] Source-agnostic: no hardcoded column names in ETL or Lambda (auto-detect or override)

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
| 17 | Pipeline only works with IEEE-CIS dataset | **Auto-detection engine** in `schema_utils.py` infers column roles from any CSV/Parquet/JSON | Day 2 |
| 18 | Hardcoded filename `train_transaction.csv` | Glue job now **discovers data files dynamically** in raw bucket | Day 2 |
| 19 | Lambda hardcoded columns can't read other datasets | Read `_schema.json` from clean bucket, build **dynamic feature matrix** | Day 4 |
| 20 | No way to upload data from browser | **Presigned URL Lambda + API Gateway + S3 CORS** for direct browser upload | Day 6 |
| 21 | No visibility into pipeline progress | **Status Lambda** checks Glue/Crawler/S3 states, **frontend polls** via API Gateway | Day 6 |
| 22 | CORS blocks browser-to-S3 uploads | Add **CORS rule** on raw bucket allowing PUT from CloudFront origin + localhost | Day 6 |

---

## Actual Pipeline Results

```
Source file:    Any CSV/Parquet/JSON (tested with IEEE-CIS 590K records)
Auto-detect:    Transaction ID, amount, timestamp, card number, address, product code
Features:      Dynamic based on detected columns (6 features from IEEE-CIS)
Glue ETL:      590,540 records processed, partitioned by year/month/region into Parquet
Crawlers:      3 tables in payflow_db (clean, scored, top_anomalies_csv)
Lambda ML:     590,540 records scored, 11,811 anomalies flagged (2.00% rate)
SNS Alert:     Email sent to kaushiik.23cs@kct.ac.in
Athena:        All 4 queries returning correct results
QuickSight:    Dashboard setup via AWS native BI tool
Frontend:      Upload portal + pipeline status + results viewer via CloudFront
API Gateway:   3 endpoints (upload-url, pipeline-status, results) — no auth, CORS enabled
```

---

## Labs from Syllabus Covered

| Lab No. | Lab Name | Used Where |
|---------|----------|-----------|
| 8 | RESTful API with Lambda + API Gateway | Day 6 — Upload/status/results API + Frontend |
| 9 | Lambda + DynamoDB | Lambda execution |
| 12 | S3 event triggers + Lambda | EventBridge → Lambda → Glue orchestration |
| 13 | Data ingestion using Glue + S3 | Day 2 — ETL pipeline |
| 14 | Glue Crawler | Day 2 — Auto-catalog data |
| 15 | Amazon Athena | Day 3 — Business queries |
| 16 | Columnar formats + cost optimization | Day 2 — Parquet output |
| 17 | AWS Lake Formation | Day 3 — Data lake governance |
| 18 | AWS Glue DataBrew | Day 2 — Data preparation |
| 19 | Amazon QuickSight | Day 5 — Dashboard |
| 25 | Cost optimization | Parquet + partition pruning + ECR + CloudFront |

---

*PayFlow — Built by Kaushiik Arul | github.com/Kaushiik-13/PayFlow*