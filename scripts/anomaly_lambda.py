import boto3
import io
import os
import json
import traceback

import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

s3  = boto3.client('s3')
sns = boto3.client('sns', region_name=os.environ['REGION'])

CLEAN_BUCKET  = os.environ['CLEAN_BUCKET']
SCORED_BUCKET = os.environ['SCORED_BUCKET']
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']

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
                body_bytes = resp['Body'].read()
                chunk = pd.read_parquet(io.BytesIO(body_bytes), columns=COLUMNS)
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
        print("Reading clean data from S3...")
        df = _read_parquet_from_bucket(CLEAN_BUCKET)
        print(f"Loaded {len(df):,} records")

        features = pd.DataFrame()

        features['txn_velocity'] = df['txn_velocity'].fillna(0).astype(float)

        features['amount_z_score'] = (
            (df['amount'].astype(float) - df['merchant_avg_amount'].astype(float)) /
            (df['merchant_avg_amount'].astype(float).std() + 1e-9)
        )

        features['geo_jump_score'] = df['geo_flag'].fillna(0).astype(float)

        features['hour_risk_score'] = df['transaction_hour'].apply(
            lambda h: 1.5 if (pd.notna(h) and (h >= 23 or h <= 4)) else 1.0
        )

        features['amount_bucket_enc'] = df['amount_bucket'].map(
            {'low': 0, 'medium': 1, 'high': 2}
        ).fillna(0).astype(float)

        features['is_weekend'] = df['is_weekend'].fillna(0).astype(float)

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

        scored_columns = [
            'TransactionID', 'amount', 'anomaly_score', 'is_anomaly',
            'geo_flag', 'transaction_hour', 'amount_bucket',
            'txn_velocity', 'ProductCD', 'year', 'month', 'day', 'region'
        ]
        df_scored = df[scored_columns].copy()

        del df, features, X, raw_scores, model, scaler
        print("Garbage collected intermediate data.")

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

        top_anomalies = df_scored[df_scored['is_anomaly'] == 1].nlargest(1000, 'anomaly_score')[[
            'TransactionID', 'amount', 'anomaly_score',
            'geo_flag', 'transaction_hour', 'amount_bucket',
            'txn_velocity', 'ProductCD'
        ]]

        csv_buffer = io.StringIO()
        top_anomalies.to_csv(csv_buffer, index=False)
        s3.put_object(
            Bucket=SCORED_BUCKET,
            Key='top_anomalies.csv',
            Body=csv_buffer.getvalue()
        )

        total   = len(df_scored)
        flagged = int(df_scored['is_anomaly'].sum())

        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject='[PayFlow] Anomaly Detection Complete',
            Message=f"""
PayFlow -- Anomaly Detection Report
===================================
Records scored     : {total:,}
Anomalies flagged  : {flagged:,}
Anomaly rate       : {flagged/total*100:.2f}%

Full results  : s3://{SCORED_BUCKET}/scored/
Top anomalies : s3://{SCORED_BUCKET}/top_anomalies.csv
            """
        )

        return {
            'statusCode': 200,
            'body': json.dumps({
                'total_scored'       : total,
                'anomalies_detected' : flagged,
                'anomaly_rate_pct'   : round(flagged/total*100, 2)
            })
        }

    except Exception as e:
        print(f"ERROR: {traceback.format_exc()}")
        raise e