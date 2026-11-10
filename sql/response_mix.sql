-- Response labels stay independent of recorded timely flags.
SELECT received_month AS month, "Company response to consumer" AS response,
 response_missing, count(*) complaints,
 count(*) FILTER (WHERE "Timely response?"='Yes') timely,
 count(*) FILTER (WHERE "Timely response?"='No') untimely,
 count(*) FILTER (WHERE "Timely response?" IS NULL OR "Timely response?" NOT IN ('Yes','No')) unknown
FROM selected_complaints GROUP BY received_month,"Company response to consumer",response_missing
ORDER BY month,response;
