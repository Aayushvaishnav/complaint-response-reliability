CREATE OR REPLACE VIEW validated_source AS
SELECT *,
    TRY_STRPTIME("Date received", '%Y-%m-%d')::DATE AS received_date,
    TRY_STRPTIME("Date sent to company", '%Y-%m-%d')::DATE AS sent_date,
    CASE
        WHEN "Timely response?" = 'Yes' THEN 'Yes'
        WHEN "Timely response?" = 'No' THEN 'No'
        ELSE 'Unknown'
    END AS timely_response_status
FROM raw_complaints;

CREATE OR REPLACE VIEW scoped_source AS
SELECT * FROM validated_source
WHERE received_date >= DATE '2023-01-01'
  AND received_date < DATE '2026-01-01';
