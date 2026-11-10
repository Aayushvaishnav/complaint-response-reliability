-- Compact independent input for the exact-arithmetic longitudinal reference.
SELECT Company AS company, Product AS product, Issue AS issue,
 received_month AS month, count(*) complaints,
 count(*) FILTER (WHERE "Timely response?" IN ('Yes','No')) known,
 count(*) FILTER (WHERE "Timely response?"='No') untimely
FROM selected_complaints GROUP BY Company,Product,Issue,received_month;
