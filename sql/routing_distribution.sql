-- Discrete routing-lag counts permit median reconciliation without row exports.
SELECT received_month AS month, routing_status, routing_days, count(*) complaints
FROM selected_complaints GROUP BY received_month,routing_status,routing_days
ORDER BY month,routing_status,routing_days;
