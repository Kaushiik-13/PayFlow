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

df = df.dropDuplicates(['TransactionID'])

df = df.withColumn('amount', F.col('TransactionAmt').cast('double'))
df = df.filter(F.col('amount') > 0)

df = df.withColumn('card_masked',
    F.concat(F.lit('****-****-****-'),
    F.substring(F.col('card1').cast('string'), -4, 4)))

df = df.withColumn('transaction_hour',
    (F.col('TransactionDT') / 3600 % 24).cast('int'))
df = df.withColumn('is_weekend',
    ((F.col('TransactionDT') / 86400 % 7) >= 5).cast('int'))

df = df.withColumn('amount_bucket',
    F.when(F.col('amount') < 50, 'low')
     .when(F.col('amount') < 500, 'medium')
     .otherwise('high'))

window_card = Window.partitionBy('card1', 'transaction_hour')
df = df.withColumn('txn_velocity',
    F.count('TransactionID').over(window_card))

window_merchant = Window.partitionBy('ProductCD')
df = df.withColumn('merchant_avg_amount',
    F.avg('amount').over(window_merchant))
df = df.withColumn('amount_deviation',
    F.abs(F.col('amount') - F.col('merchant_avg_amount')) /
    (F.col('merchant_avg_amount') + F.lit(1e-9)))

df = df.withColumn('geo_flag',
    (F.col('addr1') != F.col('addr2')).cast('int'))

from pyspark.sql.types import StringType
regions = ['ap-south-1', 'us-east-1', 'eu-west-1']
region_udf = F.udf(lambda x: regions[x % 3], StringType())
df = df.withColumn('year', F.lit(2024))
df = df.withColumn('month',
    (F.col('TransactionDT') / 2592000 % 12 + 1).cast('int'))
df = df.withColumn('day',
    (F.col('TransactionDT') / 86400 % 30 + 1).cast('int'))
df = df.withColumn('region',
    region_udf(F.col('TransactionID') % 3))

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