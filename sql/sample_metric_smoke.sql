SELECT COUNT(*) AS complaints,
    COUNT(*) FILTER (WHERE timely_response_status = 'Yes') AS timely,
    COUNT(*) FILTER (WHERE timely_response_status = 'No') AS untimely,
    COUNT(*) FILTER (WHERE timely_response_status = 'Unknown') AS unknown,
    COUNT(*) FILTER (WHERE timely_response_status IN ('Yes', 'No')) AS known,
    COUNT(*) FILTER (WHERE timely_response_status = 'Yes')::DOUBLE
        / NULLIF(COUNT(*) FILTER (WHERE timely_response_status IN ('Yes', 'No')), 0) AS timely_rate,
    COUNT(*) FILTER (WHERE timely_response_status = 'No')::DOUBLE
        / NULLIF(COUNT(*) FILTER (WHERE timely_response_status IN ('Yes', 'No')), 0) AS untimely_rate,
    COUNT(*) FILTER (WHERE timely_response_status = 'Unknown')::DOUBLE
        / NULLIF(COUNT(*), 0) AS unknown_rate,
    COUNT(*) FILTER (WHERE sent_date >= received_date) AS valid_lags,
    MEDIAN(CASE WHEN sent_date >= received_date
        THEN date_diff('day', received_date, sent_date) END) AS median_routing_days
FROM scoped_source
WHERE {filter_sql};
