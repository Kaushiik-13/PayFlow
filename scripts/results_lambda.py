import boto3
import io
import os
import json
import csv

s3 = boto3.client('s3')
SCORED_BUCKET = os.environ['SCORED_BUCKET']


def lambda_handler(event, context):
    try:
        query = event.get('queryStringParameters') or {}
        if query.get('download') == 'true':
            presigned = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': SCORED_BUCKET, 'Key': 'top_anomalies.csv'},
                ExpiresIn=300
            )
            return {
                'statusCode': 302,
                'headers': {
                    'Location': presigned,
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET,OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type'
                }
            }

        # Read _summary.json
        summary = {}
        try:
            resp = s3.get_object(Bucket=SCORED_BUCKET, Key='_summary.json')
            summary = json.loads(resp['Body'].read().decode('utf-8'))
        except Exception:
            summary = {
                'total_scored': 0, 'anomalies_detected': 0,
                'anomaly_rate_pct': 0, 'source_file': 'unknown',
                'features_used': []
            }

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
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps({'summary': summary, 'top_anomalies': top_anomalies})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps({'error': str(e)})
        }