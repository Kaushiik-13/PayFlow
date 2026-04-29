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
    '.py': 'glue-scripts',
}

def upload_file(local_path, bucket, key):
    s3.upload_file(local_path, bucket, key)
    print(f'Uploaded s3://{bucket}/{key}')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python upload_to_s3.py <local_file> [s3_suffix]')
        print('Example: python upload_to_s3.py data/my_data.csv')
        print('Example: python upload_to_s3.py data/my_data.csv raw-transactions')
        print('Example: python upload_to_s3.py scripts/glue_etl_job.py glue-scripts')
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