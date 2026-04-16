SELECT
  transaction_hour,
  COUNT(*) AS txn_volume,
  ROUND(AVG(amount), 2) AS avg_amount,
  SUM(geo_flag) AS geo_flagged_count
FROM payflow_db.clean_transactions
GROUP BY transaction_hour
ORDER BY transaction_hour;