-- Raw labels remain unchanged; tagged bucket keys cannot collide with real labels
CREATE OR REPLACE TABLE complaints AS
WITH typed AS (
 SELECT "Date received", "Product", "Sub-product", "Issue", "Sub-issue",
 "Company public response", "Company", "State", "ZIP code", "Tags", "Submitted via",
 "Date sent to company", "Company response to consumer", "Timely response?", "Complaint ID",
 CASE WHEN regexp_full_match("Date received", '[0-9]{4}-[0-9]{2}-[0-9]{2}') THEN TRY_STRPTIME("Date received", '%Y-%m-%d')::DATE END AS received_date,
 CASE WHEN regexp_full_match("Date sent to company", '[0-9]{4}-[0-9]{2}-[0-9]{2}') THEN TRY_STRPTIME("Date sent to company", '%Y-%m-%d')::DATE END AS sent_date
 FROM scoped_input
)
SELECT *, "Complaint ID" AS complaint_id,
 CASE WHEN "Timely response?" IN ('Yes','No') THEN "Timely response?" ELSE 'Unknown' END AS timely_response_status,
 CASE WHEN received_date IS NULL OR sent_date IS NULL THEN 'missing_or_invalid'
      WHEN sent_date < received_date THEN 'negative' ELSE 'valid' END AS routing_status,
 CASE WHEN sent_date >= received_date THEN date_diff('day', received_date, sent_date) END AS routing_days,
 date_trunc('month', received_date)::DATE AS received_month,
 CASE WHEN received_date IS NULL THEN 'unknown'
      WHEN received_date < DATE '2023-08-24' THEN 'pre_2023_08_24' ELSE 'post_2023_08_24' END AS taxonomy_era,
 COALESCE(received_date NOT BETWEEN DATE '2023-08-01' AND DATE '2023-08-31', false) AS longitudinal_eligible,
 COALESCE("Product", '') = '' AS product_missing,
 CASE WHEN COALESCE("Product", '') = '' THEN 'missing:' ELSE 'value:' || "Product" END AS product_bucket,
 COALESCE("Sub-product", '') = '' AS sub_product_missing,
 CASE WHEN COALESCE("Sub-product", '') = '' THEN 'missing:' ELSE 'value:' || "Sub-product" END AS sub_product_bucket,
 COALESCE("Issue", '') = '' AS issue_missing,
 CASE WHEN COALESCE("Issue", '') = '' THEN 'missing:' ELSE 'value:' || "Issue" END AS issue_bucket,
 COALESCE("Sub-issue", '') = '' AS sub_issue_missing,
 CASE WHEN COALESCE("Sub-issue", '') = '' THEN 'missing:' ELSE 'value:' || "Sub-issue" END AS sub_issue_bucket,
 COALESCE("Company public response", '') = '' AS public_response_missing,
 CASE WHEN COALESCE("Company public response", '') = '' THEN 'missing:' ELSE 'value:' || "Company public response" END AS public_response_bucket,
 COALESCE("Company", '') = '' AS company_missing,
 CASE WHEN COALESCE("Company", '') = '' THEN 'missing:' ELSE 'value:' || "Company" END AS company_bucket,
 COALESCE("State", '') = '' AS state_missing,
 CASE WHEN COALESCE("State", '') = '' THEN 'missing:' ELSE 'value:' || "State" END AS state_bucket,
 COALESCE("ZIP code", '') = '' AS zip_missing,
 CASE WHEN COALESCE("ZIP code", '') = '' THEN 'missing:' ELSE 'value:' || "ZIP code" END AS zip_bucket,
 COALESCE("Tags", '') = '' AS tags_missing,
 CASE WHEN COALESCE("Tags", '') = '' THEN 'missing:' ELSE 'value:' || "Tags" END AS tags_bucket,
 COALESCE("Submitted via", '') = '' AS submitted_via_missing,
 CASE WHEN COALESCE("Submitted via", '') = '' THEN 'missing:' ELSE 'value:' || "Submitted via" END AS submitted_via_bucket,
 COALESCE("Company response to consumer", '') = '' AS response_missing,
 CASE WHEN COALESCE("Company response to consumer", '') = '' THEN 'missing:' ELSE 'value:' || "Company response to consumer" END AS response_bucket
FROM typed;
