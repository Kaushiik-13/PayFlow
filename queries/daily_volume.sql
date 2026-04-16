SELECT
  year, month, day,
  COUNT(*) AS txn_count,
  ROUND(SUM(amount), 2) AS total_amount,
  ROUND(AVG(amount), 2) AS avg_amount
FROM payflow_db.clean_transactions
GROUP BY year, month, day
ORDER BY year, month, day;