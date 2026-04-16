SELECT
  ProductCD AS merchant_category,
  COUNT(*) AS total_txns,
  ROUND(SUM(amount), 2) AS settlement_amount,
  ROUND(AVG(amount), 2) AS avg_txn_value
FROM payflow_db.clean_transactions
WHERE isFraud = 0
GROUP BY ProductCD
ORDER BY settlement_amount DESC;