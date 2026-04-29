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
sns = boto3.client('sns', region_name=os.environ['REGION'])

CLEAN_BUCKET  = os.environ['CLEAN_BUCKET']
SCORED_BUCKET = os.environ['SCORED_BUCKET']
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']


def _read_schema(bucket):
    try:
        resp = s3.get_object(Bucket=bucket, Key='clean/_schema.json/part-00000')
        return json.loads(resp['Body'].read().decode('utf-8').strip())
    except Exception:
        pass
    try:
        resp = s3.get_object(Bucket=bucket, Key='clean/_schema.json')
        return json.loads(resp['Body'].read().decode('utf-8'))
    except Exception:
        return None


def _build_column_list(schema):
    columns = set()
    roles = schema.get('column_roles', {})
    for canonical, source in roles.items():
        columns.add(source)
    features = schema.get('detected_features', [])
    columns.update(features)
    columns.update(['year', 'month', 'region', 'day'])
    return list(columns)


def _read_parquet_from_bucket(bucket, columns=None):
    paginator = s3.get_paginator('list_objects_v2')
    dfs = []
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if key.endswith('.parquet'):
                resp = s3.get_object(Bucket=bucket, Key=key)
                body_bytes = resp['Body'].read()
                read_kwargs = {}
                if columns:
                    available_cols = [c for c in columns if c not in ('year', 'month', 'region')]
                    read_kwargs['columns'] = available_cols
                chunk = pd.read_parquet(io.BytesIO(body_bytes), **read_kwargs)
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
    features = pd.DataFrame()
    available = set(df.columns)

    if 'txn_velocity' in available:
        features['txn_velocity'] = df['txn_velocity'].fillna(0).astype(float)

    if 'amount' in available and 'merchant_avg_amount' in available:
        features['amount_z_score'] = (
            (df['amount'].astype(float) - df['merchant_avg_amount'].astype(float)) /
            (df['merchant_avg_amount'].astype(float).std() + 1e-9)
        )

    if 'geo_flag' in available:
        features['geo_jump_score'] = df['geo_flag'].fillna(0).astype(float)

    if 'transaction_hour' in available:
        features['hour_risk_score'] = df['transaction_hour'].apply(
            lambda h: 1.5 if (pd.notna(h) and (h >= 23 or h <= 4)) else 1.0
        )

    if 'amount_bucket' in available:
        features['amount_bucket_enc'] = df['amount_bucket'].map(
            {'low': 0, 'medium': 1, 'high': 2}
        ).fillna(0).astype(float)

    if 'is_weekend' in available:
        features['is_weekend'] = df['is_weekend'].fillna(0).astype(float)

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
            df = _read_parquet_from_bucket(CLEAN_BUCKET)

        print(f"Loaded {len(df):,} records")

        features = _build_features(df, schema or {})

        if features.empty or len(features.columns) == 0:
            raise ValueError("No features could be constructed from the available data. "
                           "Ensure the source data has at least an amount column.")

        print(f"Using {len(features.columns)} features: {list(features.columns)}")

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

        scored_columns = ['TransactionID', 'amount', 'anomaly_score', 'is_anomaly',
                          'geo_flag', 'transaction_hour', 'amount_bucket',
                          'txn_velocity', 'ProductCD', 'year', 'month', 'day', 'region']
        available_scored = [c for c in scored_columns if c in df.columns]
        for core_col in ['anomaly_score', 'is_anomaly', 'year', 'month', 'region']:
            if core_col not in available_scored and core_col in df.columns:
                available_scored.append(core_col)
        df_scored = df[available_scored].copy()

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

        source_file = schema.get('source_file', 'unknown') if schema else 'unknown'
        features_used = list(features.columns) if 'features' in dir() else []

        summary = {
            'total_scored': total,
            'anomalies_detected': flagged,
            'anomaly_rate_pct': round(flagged/total*100, 2) if total > 0 else 0,
            'source_file': source_file,
            'features_used': features_used,
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
                'features_used'      : features_used,
                'source_file'        : source_file
            })
        }

    except Exception as e:
        print(f"ERROR: {traceback.format_exc()}")
        raise e