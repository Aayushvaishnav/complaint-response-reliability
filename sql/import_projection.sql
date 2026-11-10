-- Null-safe raw joins preserve SQL NULL, empty strings and literal display labels separately
CREATE OR REPLACE TEMP TABLE complaint_cohorts AS
SELECT s.received_date,c.company_key,p.product_key,i.issue_key,g.geography_key,
s.routing_status,s.routing_days,count(*)::BIGINT complaint_rows,
count(*) FILTER(WHERE timely_response_status='Yes')::BIGINT yes_rows,
count(*) FILTER(WHERE timely_response_status='No')::BIGINT no_rows,
count(*) FILTER(WHERE timely_response_status='Unknown')::BIGINT unknown_rows
FROM projection_input s
JOIN company c ON s.Company IS NOT DISTINCT FROM c.raw_value
JOIN product p ON s.Product IS NOT DISTINCT FROM p.raw_value
JOIN issue i ON s.Issue IS NOT DISTINCT FROM i.raw_value
JOIN geography g ON s.State IS NOT DISTINCT FROM g.raw_value
GROUP BY ALL;

CREATE OR REPLACE TEMP TABLE "date" AS
SELECT d::DATE date,year(d)::INTEGER "year",date_trunc('month',d)::DATE month_start,
strftime(d,'%Y-%m') month_label,(year(d)*100+month(d))::INTEGER month_order,
CASE WHEN d<DATE '2023-08-24' THEN 'pre_2023_08_24' ELSE 'post_2023_08_24' END timing_era,
d>=DATE '2023-08-01' AND d<DATE '2023-09-01' boundary_month
FROM generate_series(DATE '2023-01-01',DATE '2025-12-31',INTERVAL 1 DAY) t(d);

CREATE OR REPLACE TEMP TABLE review_minimum AS SELECT minimum::BIGINT minimum FROM (VALUES (50),(100),(200)) t(minimum);
CREATE OR REPLACE TEMP TABLE sensitivity_minimum AS SELECT * FROM review_minimum;
CREATE OR REPLACE TEMP TABLE review_window AS
SELECT DISTINCT month_start window_end,month_label window_label,month_order FROM "date";

-- Observed months only; any eligible three-month window must have an observed ending month
CREATE OR REPLACE TEMP TABLE review_selection AS
WITH observed AS (
 SELECT DISTINCT company_key,product_key,issue_key,date_trunc('month',received_date)::DATE window_end
 FROM complaint_cohorts), segments AS (
 SELECT company_key,product_key,issue_key,
 row_number() OVER (ORDER BY company_key,product_key,issue_key)::BIGINT segment_key
 FROM (SELECT DISTINCT company_key,product_key,issue_key FROM observed))
SELECT row_number() OVER (ORDER BY segment_key,window_end)::BIGINT selection_key,
segment_key,o.company_key,o.product_key,o.issue_key,o.window_end,
c.raw_value company_raw,p.raw_value product_raw,i.raw_value issue_raw,
c.display_label company,p.display_label product,i.display_label issue,
c.missingness company_missingness,p.missingness product_missingness,i.missingness issue_missingness
FROM observed o JOIN segments USING(company_key,product_key,issue_key)
JOIN company c USING(company_key) JOIN product p USING(product_key) JOIN issue i USING(issue_key);
