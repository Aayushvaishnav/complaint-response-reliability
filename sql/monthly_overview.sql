-- Received-month descriptive cohorts; August remains in all totals.
SELECT received_month AS month, count(*) complaints,
 count(*) FILTER (WHERE "Timely response?"='Yes') timely,
 count(*) FILTER (WHERE "Timely response?"='No') untimely,
 count(*) FILTER (WHERE "Timely response?" IN ('Yes','No')) known,
 count(*) FILTER (WHERE "Timely response?" IS NULL OR "Timely response?" NOT IN ('Yes','No')) unknown,
 count(routing_days) valid_routing,
 median(routing_days) median_routing_days,
 count(*) FILTER (WHERE routing_status='negative') negative_routing,
 count(*) FILTER (WHERE routing_status='missing_or_invalid') missing_invalid_routing
FROM selected_complaints GROUP BY received_month ORDER BY month;
