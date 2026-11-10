WITH ranked_ids AS (
    SELECT "Complaint ID",
        ROW_NUMBER() OVER (
            PARTITION BY strftime(received_date, '%Y-%m'), "Product", "Timely response?"
            ORDER BY "Complaint ID"
        ) AS stratum_position
    FROM scoped_source
), selected_ids AS (
    SELECT "Complaint ID" FROM ranked_ids WHERE stratum_position <= $rows_per_stratum
)
SELECT source.* EXCLUDE (received_date, sent_date, timely_response_status)
FROM scoped_source AS source
INNER JOIN selected_ids USING ("Complaint ID")
ORDER BY "Date received", "Complaint ID";
