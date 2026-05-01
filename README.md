# PayFlow — Payment Transaction Anomaly Detection Pipeline

AWS serverless ETL pipeline that ingests 590K+ payment transactions, enriches and cleanes them via Glue PySpark, governs access through Lake Formation, and runs an **unsupervised Isolation Forest ML model** on a Lambda Container Image to flag fraudulent anomalies — all orchestrated by EventBridge, queried by Athena, and visualized on QuickSight **and a web portal**.

---

## Architecture

```
Raw CSV / Browser Upload
        |
        v
   S3 Raw Zone ──── EventBridge ──── Lambda (glue-trigger) ──── Glue ETL Job
                                                                      |
                                                              Clean + Feature Engineer
                                                                      |
                                                                      v
   S3 Clean Zone (Parquet, partitioned by year/month/region)
        |
        v
   EventBridge ──── Lambda (crawler-trigger) ──── Glue Crawlers ──── Data Catalog
                                                                          |
                                                                     Athena Queries
                                                                          |
         +----------------------------------------------------------+
         |                              |                             |
         v                              v                             v
   Lambda ML (Isolation Forest)    SNS Alert Email          QuickSight Dashboard
         |
         v
   S3 Scored Zone (Parquet) + top_anomalies.csv
         |
         v
   Web Portal (S3 + CloudFront) ← API Gateway ← Lambda (status, results, upload)
```

---

## Pipeline Results

| Metric | Value |
|--------|-------|
| Records processed | 590,540 |
| Anomalies flagged | 11,807 |
| Anomaly detection rate | 2.00% |
| ETL runtime | ~5 min (2 G.1X workers) |
| Lambda cold start | ~45-60s |
| Lambda warm execution | ~50s |
| Pipeline cost (1 week) | ~$0.61 |

---

## Live Endpoints

| Component | URL |
|-----------|-----|
| Web Portal | `https://d223k5rhdipe2a.cloudfront.net` |
| API Gateway | `https://4c6dzan5xb.execute-api.ap-south-1.amazonaws.com/prod` |
| API Routes | `GET /pipeline-status`, `GET /results`, `POST /upload-url` |

---

## Tech Stack

| Layer | Service | Purpose | Cost |
|-------|---------|---------|------|
| Infrastructure | Terraform | IaC provisioning | Free |
| Orchestration | EventBridge + Lambda | Pipeline triggers | ~$0.00 |
| Storage | S3 (5 buckets) | Raw, clean, scored, Athena, scripts | ~$0.05 |
| ETL | Glue PySpark | Clean, enrich, partition | ~$0.30 |
| Cataloging | Glue Crawler | Auto-discover schema | ~$0.05 |
| Governance | Lake Formation | Database-level permissions | Free |
| Querying | Athena | SQL on scored data | ~$0.10 |
| ML | Lambda Container (Isolation Forest) | Anomaly scoring | ~$0.00 |
| Registry | ECR | Container image storage | ~$0.05 |
| Alerts | SNS | Email notifications | ~$0.00 |
| Error Handling | SQS DLQ | Failed invocation capture | ~$0.00 |
| Dashboard | QuickSight | BI visualization | Free trial |
| CI/CD | GitHub Actions | Terraform validation | Free |
| **Total** | | **1 week** | **~$0.61** |

---

## Quick Start

### Prerequisites
- AWS CLI configured with `ap-south-1` region
- Terraform >= 1.6
- Docker Desktop (running)
- Kaggle API or manual download of IEEE-CIS dataset

### Quick Start

#### Prerequisites
- AWS CLI configured with `ap-south-1` region
- Terraform >= 1.6
- Docker Desktop (running)
- Kaggle API or manual download of IEEE-CIS dataset

#### Deploy Everything

```bash
# 1. Bootstrap Terraform backend (run once)
aws s3api create-bucket --bucket payflow-tfstate-104573823385 --region ap-south-1 \
  --create-bucket-configuration LocationConstraint=ap-south-1
aws s3api put-bucket-versioning --bucket payflow-tfstate-104573823385 \
  --versioning-configuration Status=Enabled
aws dynamodb create-table --table-name payflow-terraform-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST --region ap-south-1

# 2. Provision infrastructure
cd terraform
terraform init
terraform plan
terraform apply -auto-approve

# 3. Build & push Lambda container image
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin 104573823385.dkr.ecr.ap-south-1.amazonaws.com
aws ecr create-repository --repository-name payflow-anomaly-detector --region ap-south-1
docker buildx build --platform linux/amd64 --provenance=false \
  -t 104573823385.dkr.ecr.ap-south-1.amazonaws.com/payflow-anomaly-detector:latest --push ../scripts/

# 4. Update Lambda with new image
aws lambda update-function-code --function-name payflow-anomaly-detector \
  --image-uri 104573823385.dkr.ecr.ap-south-1.amazonaws.com/payflow-anomaly-detector:latest \
  --region ap-south-1

# 5. Upload data and ETL script
aws s3 cp ../scripts/glue_etl_job.py s3://payflow-glue-scripts-dev-104573823385/
aws s3 cp ../scripts/schema_utils.py s3://payflow-glue-scripts-dev-104573823385/
aws s3 cp ../data/train_transaction.csv s3://payflow-raw-transactions-dev-104573823385/

# 6. Run the pipeline (or use the web portal at https://d223k5rhdipe2a.cloudfront.net)
aws glue start-job-run --job-name payflow-etl-job --region ap-south-1
# Wait ~5 min, then:
aws glue start-crawler --name payflow-clean-crawler --region ap-south-1
# After crawler, invoke Lambda:
aws lambda invoke --function-name payflow-anomaly-detector --region ap-south-1 \
  --cli-binary-format raw-in-base64-out --payload '{}' response.json

# 7. Run scored crawler
aws glue start-crawler --name payflow-scored-crawler --region ap-south-1

# 8. Upload frontend files (if not auto-deployed)
aws s3 sync ../frontend/ s3://payflow-frontend-dev-104573823385/
```

#### Browser Upload (Alternative to CLI)
1. Open `https://d223k5rhdipe2a.cloudfront.net`
2. Drag & drop a CSV/Parquet/JSON file onto the upload panel
3. Pipeline auto-triggers via EventBridge — monitor progress in real-time
4. View anomaly results in the results table once complete

---

## Data Flow

### 1. Ingestion
Raw CSV/Parquet/JSON is uploaded to `s3://payflow-raw-transactions-dev-104573823385/` via CLI or browser drag-and-drop. Column roles are auto-detected using keyword heuristics (`schema_utils.py`).

### 2. Glue ETL (PySpark)
- **Auto-discovers** data files using boto3 (no hardcoded paths)
- **Auto-detects** column roles (transaction_id, amount, timestamp, card, etc.)
- Renames columns to canonical names (`TransactionID` → `transaction_id`)
- Deduplicates by `transaction_id`
- Masks credit card numbers → `card_masked`
- Engineers features: `transaction_hour`, `is_weekend`, `amount_bucket`, `txn_velocity`, `merchant_avg_amount`, `amount_deviation`, `geo_flag`
- Partitions by `year`, `month`, `region`
- Writes Parquet to `s3://payflow-clean-transactions-dev-104573823385/clean/`
- Writes `_schema.json` metadata for downstream consumers

### 3. Cataloging
Two Glue Crawlers discover tables in `payflow_db`:
- `payflow_clean_transactions_dev_104573823385` (clean data)
- `scored` (anomaly-scored data)
- `top_anomalies_csv` (top 1000 suspicious transactions)

### 4. Anomaly Detection (Isolation Forest)
Lambda Container Image reads `_schema.json` to determine available columns, then reads only needed columns from partitioned Parquet files. Trains an Isolation Forest model with:
- `contamination=0.02` (matches ~2% fraud rate)
- `n_estimators=100`, `n_jobs=1` (single vCPU)
- Features: `txn_velocity`, `amount_z_score`, `geo_jump_score`, `hour_risk_score`, `amount_bucket_enc`, `is_weekend`

Outputs:
- Scored Parquet (with `anomaly_score` 0-100 and `is_anomaly` 0/1) to `scored/` prefix
- `top_anomalies.csv` (top 1000 most suspicious transactions)
- SNS email alert with summary statistics

### 5. Querying & Visualization
Athena queries on scored data via `payflow-workgroup` (1GB scan limit). QuickSight dashboard for business users.

---

## Project Structure

```
payflow/
├── terraform/
│   ├── main.tf                    # Module orchestration (10 modules)
│   ├── variables.tf               # account_id, email, region, frontend_domain
│   ├── outputs.tf                 # Bucket names, role ARNs, URLs
│   ├── backend.tf                 # S3 remote state
│   └── modules/
│       ├── s3/                    # 6 buckets + versioning + EventBridge + CORS
│       ├── iam/                   # 5 roles (glue, lambda, eventbridge, api) + policies
│       ├── glue/                  # Database + ETL job + 2 crawlers
│       ├── lambda/                # Container function + SNS + SQS DLQ
│       ├── eventbridge/           # 2 rules + 2 Lambda triggers
│       ├── lake_formation/        # Data lake settings + permissions
│       ├── athena/                # Workgroup (1GB scan limit)
│       ├── api_gateway/           # HTTP API + routes + CORS + deployment
│       ├── api_lambdas/           # 3 inline Lambda functions (presigned URL, status, results)
│       └── frontend/              # CloudFront distribution + OAC + S3 origin
├── scripts/
│   ├── glue_etl_job.py            # Source-agnostic PySpark ETL + auto-detection
│   ├── schema_utils.py            # Column role heuristics engine
│   ├── anomaly_lambda.py          # Isolation Forest ML (container image)
│   ├── presigned_url_lambda.py    # Presigned URL generator for browser uploads
│   ├── pipeline_status_lambda.py  # Pipeline status checker
│   ├── results_lambda.py          # Anomaly results fetcher
│   ├── Dockerfile                  # Lambda container definition
│   └── validate_data.py           # Dataset validation
├── frontend/
│   ├── index.html                 # Web portal UI
│   ├── styles.css                 # Portal styling
│   └── app.js                     # Portal logic (API calls, drag-drop upload)
├── queries/
│   ├── daily_volume.sql
│   ├── fraud_merchants.sql
│   ├── settlement_report.sql
│   └── peak_hours.sql
├── .github/workflows/terraform.yml
└── payflow-implementation-plan.md # Detailed 5-day plan with fixes
```

---

## Key Learnings

Building this pipeline on AWS taught us several non-obvious lessons:

| # | What We Hit | The Fix |
|---|-------------|---------|
| 1 | EventBridge can't target Glue jobs/crawlers (400 error) | Lambda intermediary functions that call `glue:start_job_run()` and `glue:startCrawler()` |
| 2 | `AWS_REGION` is a reserved Lambda env var | Use `REGION` instead |
| 3 | Docker multi-arch manifests break Lambda | Build with `--platform linux/amd64 --provenance=false` |
| 4 | S3 streaming Body doesn't support `seek()` | Read bytes first: `io.BytesIO(resp['Body'].read())` |
| 5 | Partition columns can't be projected in `pd.read_parquet(columns=...)` | Extract from S3 key paths instead |
| 6 | 590K rows × 394 columns OOMs at 3GB Lambda | Read only needed columns, write scored data in partitions |
| 7 | Glue `parquet()` fails with "Can not create a Path from empty string" | Write to `clean/` prefix, filter null partitions |
| 8 | Lake Formation table permissions fail before tables exist | Use database-level permissions (`ALL` for admin, `DESCRIBE` for analyst) |
| 9 | Lambda needs `sqs:SendMessage` for DLQ | Add inline policy alongside `sns:Publish` |
| 10 | Glue Crawler doesn't emit completion events | Invoke Lambda manually after crawlers finish |
| 11 | Hadoop `FileSystem.listStatus()` fails in Glue 4.0 with `Wrong FS: s3://, expected: file:///` | Use boto3 S3 client for file discovery instead of JVM Hadoop calls |
| 12 | `saveAsTextFile()` fails with `ClassNotFoundException: DirectOutputCommitter` in Glue 4.0 | Use boto3 `put_object()` to write JSON metadata files |
| 13 | Anomaly Lambda looks for original column names (`TransactionID`) but ETL renames to canonical (`transaction_id`) | Use canonical column names from `_schema.json` when reading clean parquet files |
| 14 | Windows PowerShell strips quotes from JSON arguments | Escape with `\"` or use `--cli-binary-format raw-in-base64-out` |
| 15 | AWS CLI `--name` vs `--job-name` parameter mismatch on Windows | Use exact parameter names from AWS CLI docs |
| 16 | Terraform `path.module` fails on Windows with inline heredoc Lambda code | Use `<<-EOT` heredoc syntax in `main.tf` instead of `templatefile()` |
| 17 | API Gateway v2 HTTP API requires `POST` for Lambda proxy integrations | Set `integration_method = "POST"` on all routes |
| 18 | Lambda image update not immediately available | Wait ~30s after `update-function-code` before invoking |

> See `payflow-implementation-plan.md` for the full list of 16 fixes with discovery context.

---

## Security

- **Least-privilege IAM** — scoped inline policies (no `S3FullAccess` or `SNSFullAccess`)
- **No hardcoded secrets** — all config via Terraform variables and Lambda env vars
- **S3 versioning + public access blocks** on all 5 buckets
- **Lake Formation** governance with database-level permissions
- **Athena 1GB scan limit** prevents runaway query costs
- **SQS DLQ** catches failed Lambda invocations
- **Credit card masking** in ETL (`****-****-****-1234`)
- **Terraform state** encrypted in S3 with DynamoDB locking

---

## AWS Resources Created

| Resource | Name |
|----------|------|
| S3 Buckets | `payflow-raw-transactions-dev-104573823385`, `payflow-clean-transactions-dev-104573823385`, `payflow-scored-transactions-dev-104573823385`, `payflow-athena-results-dev-104573823385`, `payflow-glue-scripts-dev-104573823385`, `payflow-frontend-dev-104573823385` |
| IAM Roles | `payflow-glue-role`, `payflow-lambda-role`, `payflow-eventbridge-role`, `payflow-glue-trigger-role`, `payflow-api-lambda-role` |
| Lambda Functions | `payflow-anomaly-detector`, `payflow-glue-trigger`, `payflow-crawler-trigger`, `presigned-url-lambda`, `pipeline-status-lambda`, `results-lambda` |
| Glue | Database `payflow_db`, Job `payflow-etl-job`, Crawlers `payflow-clean-crawler` + `payflow-scored-crawler` |
| SNS Topic | `payflow-fraud-alerts` |
| SQS Queue | `payflow-lambda-dlq` |
| Athena Workgroup | `payflow-workgroup` |
| ECR Repository | `payflow-anomaly-detector` |
| EventBridge Rules | `payflow-s3-upload-trigger`, `payflow-glue-success-trigger` |
| API Gateway | HTTP API `4c6dzan5xb` (routes: `GET /pipeline-status`, `GET /results`, `POST /upload-url`) |
| CloudFront | Distribution `d223k5rhdipe2a` (frontend S3 origin) |

---

## Labs from Syllabus Covered

| Lab | Topic | Where Used |
|-----|-------|-----------|
| 8 | RESTful API + Lambda | API Gateway + 3 Lambda functions (presigned URL, status, results) |
| 9 | Lambda + DynamoDB | Lambda execution + pipeline state |
| 12 | S3 event triggers | EventBridge → Lambda → Glue |
| 13 | Glue + S3 | ETL pipeline |
| 14 | Glue Crawler | Auto-catalog data |
| 15 | Athena | Business queries |
| 16 | Columnar formats + cost optimization | Parquet partitioning |
| 17 | Lake Formation | Data governance |
| 18 | Glue DataBrew | Data preparation |
| 19 | QuickSight | Dashboard |
| 25 | Cost optimization | Parquet + ECR + partitioning |

---

## Destroy

```bash
cd terraform
terraform destroy -auto-approve

# Delete ECR repository
aws ecr delete-repository --repository-name payflow-anomaly-detector --region ap-south-1 --force

# Delete Terraform state bucket and lock table (optional)
aws s3 rm s3://payflow-tfstate-104573823385 --recursive
aws s3api delete-bucket --bucket payflow-tfstate-104573823385 --region ap-south-1
aws dynamodb delete-table --table-name payflow-terraform-lock --region ap-south-1
```

---

Built by **Kaushiik Arul** | [github.com/Kaushiik-13/PayFlow](https://github.com/Kaushiik-13/PayFlow)