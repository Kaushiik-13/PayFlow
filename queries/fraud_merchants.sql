SELECT
  ProductCD AS merchant_category,
  COUNT(*) AS suspicious_txns,
  ROUND(SUM(amount), 2) AS total_suspicious_amount,
  ROUND(AVG(amount_deviation), 4) AS avg_deviation
FROM payflow_db.clean_transactions
WHERE geo_flag = 1
  AND amount_bucket = 'high'
GROUP BY ProductCD
ORDER BY suspicious_txns DESC
LIMIT 20;