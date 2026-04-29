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
    'SOURCE_CONFIG'
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
hadoop_conf = sc._jsc.hadoopConfiguration()
fs = sc._jvm.org.apache.hadoop.fs.FileSystem.get(sc._jsc.hadoopConfiguration())
raw_path = sc._jvm.org.apache.hadoop.fs.Path(f"s3://{raw_bucket}/")
data_files = []

for f in fs.listStatus(raw_path):
    name = f.getPath().getName()
    if name.endswith(('.csv', '.parquet', '.json')):
        data_files.append(f.getPath().toString())

if not data_files:
    raise ValueError(f"No data files (.csv/.parquet/.json) found in s3://{raw_bucket}/")

data_path = data_files[0]
file_ext = data_path.rsplit('.', 1)[-1].lower()
print(f"Auto-detected data file: {data_path} (format: {file_ext})")

# ─── Step 2: Read data based on detected format ───
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
cols = df.columns
roles = {}
used = set()

def find_by_keywords(column_list, keywords):
    for col in column_list:
        if col in used:
            continue
        if any(kw in col.lower() for kw in keywords):
            return col
    return None

# Transaction ID
if 'transaction_id' in override_mappings:
    roles['transaction_id'] = override_mappings['transaction_id']
    used.add(override_mappings['transaction_id'])
else:
    tid = find_by_keywords(cols, ['id', 'txn', 'trans'])
    if tid:
        roles['transaction_id'] = tid
        used.add(tid)
    else:
        for col in cols:
            if col not in used and df.select(col).distinct().count() == raw_count:
                roles['transaction_id'] = col
                used.add(col)
                break

# Amount
if 'amount' in override_mappings:
    roles['amount'] = override_mappings['amount']
    used.add(override_mappings['amount'])
else:
    amt = find_by_keywords(cols, ['amt', 'amount', 'price', 'total', 'value', 'sum'])
    if amt:
        roles['amount'] = amt
        used.add(amt)
    else:
        for col in cols:
            dt = dict(df.dtypes)
            if col not in used and dt.get(col) in ['double', 'int', 'bigint', 'float']:
                if df.filter(F.col(col) > 0).count() > raw_count * 0.9:
                    roles['amount'] = col
                    used.add(col)
                    break

# Timestamp
if 'timestamp' in override_mappings:
    roles['timestamp'] = override_mappings['timestamp']
    used.add(override_mappings['timestamp'])
else:
    ts = find_by_keywords(cols, ['date', 'time', 'dt', 'timestamp'])
    if ts:
        roles['timestamp'] = ts
        used.add(ts)

# Card number
if 'card_number' in override_mappings:
    roles['card_number'] = override_mappings['card_number']
    used.add(override_mappings['card_number'])
else:
    card = find_by_keywords(cols, ['card', 'pan', 'account'])
    if card:
        roles['card_number'] = card
        used.add(card)

# Address columns
for canon, keywords in [('address_1', ['addr1', 'address1', 'city', 'state']),
                         ('address_2', ['addr2', 'address2', 'zip', 'postal'])]:
    if canon in override_mappings:
        roles[canon] = override_mappings[canon]
        used.add(override_mappings[canon])
    else:
        addr = find_by_keywords(cols, keywords)
        if addr:
            roles[canon] = addr
            used.add(addr)

# Product code
if 'product_code' in override_mappings:
    roles['product_code'] = override_mappings['product_code']
    used.add(override_mappings['product_code'])
else:
    prod = find_by_keywords(cols, ['product', 'category', 'merchant', 'type'])
    if prod and df.select(prod).distinct().count() < min(100, raw_count * 0.1):
        roles['product_code'] = prod
        used.add(prod)

print(f"Detected column roles: {json.dumps(roles, indent=2)}")

# ─── Step 4: Normalize columns to canonical names ───
rename_map = {}
for canonical, source in roles.items():
    if source in df.columns and canonical != source:
        rename_map[source] = canonical

for old_name, new_name in rename_map.items():
    df = df.withColumnRenamed(old_name, new_name)

# ─── Step 5: Conditional feature engineering ───
if 'transaction_id' in df.columns:
    df = df.dropDuplicates(['transaction_id'])

if 'amount' in df.columns:
    df = df.withColumn('amount', F.col('amount').cast('double'))
    df = df.filter(F.col('amount') > 0)

if 'card_number' in df.columns:
    df = df.withColumn('card_masked',
        F.concat(F.lit('****-****-****-'),
        F.substring(F.col('card_number').cast('string'), -4, 4)))

if 'timestamp' in df.columns:
    ts_dtype = dict(df.dtypes).get('timestamp', '')
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
        df = df.withColumn('transaction_hour',
            F.hour(F.col('timestamp')).cast('int'))
        df = df.withColumn('is_weekend',
            (F.dayofweek(F.col('timestamp')).isin(1, 7)).cast('int'))
        df = df.withColumn('month', F.month(F.col('timestamp')).cast('int'))
        df = df.withColumn('day', F.dayofmonth(F.col('timestamp')).cast('int'))

if 'amount' in df.columns:
    df = df.withColumn('amount_bucket',
        F.when(F.col('amount') < 50, 'low')
         .when(F.col('amount') < 500, 'medium')
         .otherwise('high'))

if 'transaction_id' in df.columns and 'transaction_hour' in df.columns:
    window_card = Window.partitionBy('transaction_hour')
    df = df.withColumn('txn_velocity',
        F.count('transaction_id').over(window_card))

if 'product_code' in df.columns and 'amount' in df.columns:
    window_merchant = Window.partitionBy('product_code')
    df = df.withColumn('merchant_avg_amount',
        F.avg('amount').over(window_merchant))
    df = df.withColumn('amount_deviation',
        F.abs(F.col('amount') - F.col('merchant_avg_amount')) /
        (F.col('merchant_avg_amount') + F.lit(1e-9)))

if 'address_1' in df.columns and 'address_2' in df.columns:
    df = df.withColumn('geo_flag',
        (F.col('address_1') != F.col('address_2')).cast('int'))

# ─── Step 6: Partition columns ───
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

essential = [c for c in ['transaction_id', 'amount'] if c in df.columns]
if essential:
    df = df.dropna(subset=essential)
df = df.filter(F.col('region').isNotNull() & F.col('month').isNotNull() & F.col('day').isNotNull())

clean_count = df.count()
print(f"Clean records after ETL: {clean_count:,}")

if clean_count == 0:
    print("WARNING: No records after ETL. Skipping write.")
else:
    df.write \
      .mode('overwrite') \
      .partitionBy('year', 'month', 'region') \
      .parquet(f"s3://{clean_bucket}/clean/")

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
    spark.sparkContext.parallelize([json.dumps(schema_info)]).saveAsTextFile(
        f"s3://{clean_bucket}/clean/_schema.json"
    )

print("ETL job complete.")
job.commit()