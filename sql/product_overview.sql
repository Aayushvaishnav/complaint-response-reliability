-- Raw labels are separate portfolios; no taxonomy crosswalk or exposure adjustment.
SELECT Product AS product, count(*) complaints,
 count(*) FILTER (WHERE "Timely response?"='Yes') timely,
 count(*) FILTER (WHERE "Timely response?"='No') untimely,
 count(*) FILTER (WHERE "Timely response?" IN ('Yes','No')) known,
 count(*) FILTER (WHERE "Timely response?" IS NULL OR "Timely response?" NOT IN ('Yes','No')) unknown,
 count(routing_days) valid_routing, median(routing_days) median_routing_days
FROM selected_complaints GROUP BY Product ORDER BY complaints DESC, product;
