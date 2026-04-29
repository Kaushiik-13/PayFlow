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

    # Stage 1: Upload - check if raw bucket has files
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
            state = runs['JobRuns'][0]['JobRunState']
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
        clean_crawler = glue.get_crawler(Name=f'{PROJECT_NAME}-clean-crawler')['Crawler']
        clean_state = clean_crawler['State']
        if clean_state == 'READY':
            last_crawl = clean_crawler.get('LastCrawl', {})
            if last_crawl.get('Status') == 'SUCCEEDED':
                crawler_status = 'complete'
        elif 'RUNNING' in clean_state:
            crawler_status = 'running'
    except Exception:
        pass
    stages.append({'name': 'crawlers', 'status': crawler_status})

    # Stage 4: Anomaly detection - check for _summary.json
    anomaly_status = 'pending'
    try:
        s3.head_object(Bucket=SCORED_BUCKET, Key='_summary.json')
        anomaly_status = 'complete'
    except s3.exceptions.ClientError:
        try:
            scored_objects = s3.list_objects_v2(Bucket=SCORED_BUCKET, Prefix='scored/', MaxKeys=1)
            if scored_objects.get('KeyCount', 0) > 0:
                anomaly_status = 'running'
        except Exception:
            pass
    except Exception:
        pass
    stages.append({'name': 'anomaly_detection', 'status': anomaly_status})

    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET,OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        },
        'body': json.dumps({'stages': stages})
    }