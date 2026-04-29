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
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'POST,OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type'
                },
                'body': json.dumps({'error': f'Unsupported file type: {ext}. Use CSV, Parquet, or JSON.'})
            }

        presigned_url = s3.generate_presigned_url(
            'put_object',
            Params={'Bucket': RAW_BUCKET, 'Key': filename, 'ContentType': content_type},
            ExpiresIn=300
        )

        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps({'upload_url': presigned_url, 'file_key': filename})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps({'error': str(e)})
        }