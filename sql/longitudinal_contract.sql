-- Canonical input only; parameters are bound by review_contract.evaluate.
WITH scoped AS (
 SELECT * FROM contract_input
 WHERE received_date >= $start AND received_date < $end
 AND ($companies IS NULL OR list_contains(CAST($companies AS VARCHAR[]), company) OR (company IS NULL AND list_contains(list_transform(CAST($companies AS VARCHAR[]), lambda x: x IS NULL), true)))
 AND ($products IS NULL OR list_contains(CAST($products AS VARCHAR[]), product) OR (product IS NULL AND list_contains(list_transform(CAST($products AS VARCHAR[]), lambda x: x IS NULL), true)))
 AND ($states IS NULL OR list_contains(CAST($states AS VARCHAR[]), state) OR (state IS NULL AND list_contains(list_transform(CAST($states AS VARCHAR[]), lambda x: x IS NULL), true)))
), months AS (
 SELECT CAST(m AS DATE) AS month FROM generate_series(date_trunc('month', CAST($start AS DATE)), date_trunc('month', CAST($end AS DATE) - INTERVAL 1 DAY), INTERVAL 1 MONTH) t(m)
), segments AS (
 SELECT DISTINCT company, product, issue FROM scoped
), counts AS (
 SELECT company, product, issue, CAST(date_trunc('month', received_date) AS DATE) AS month,
 count(*) complaints, count(*) FILTER(WHERE timely_flag IN ('Yes','No')) known,
 count(*) FILTER(WHERE timely_flag = 'No') untimely
 FROM scoped GROUP BY ALL
), grid AS (
 SELECT s.*, m.month, coalesce(c.complaints,0) complaints, coalesce(c.known,0) known, coalesce(c.untimely,0) untimely
 FROM segments s CROSS JOIN months m LEFT JOIN counts c
 ON s.company IS NOT DISTINCT FROM c.company AND s.product IS NOT DISTINCT FROM c.product
 AND s.issue IS NOT DISTINCT FROM c.issue AND m.month=c.month
), totals AS (
 SELECT *, sum(complaints) OVER cohort total_complaints,
 sum(known) OVER cohort total_known, sum(untimely) OVER cohort total_untimely
 FROM grid WINDOW cohort AS (PARTITION BY company,product,month)
), monthly AS (
 SELECT *, total_complaints-complaints peer_complaints, total_known-known peer_known,
 total_untimely-untimely peer_untimely,
 complaints::DOUBLE/nullif(total_complaints,0) issue_share,
 month >= CAST($start AS DATE) AND month+INTERVAL 1 MONTH <= CAST($end AS DATE) complete_month,
 CASE WHEN month < DATE '2023-08-01' THEN 'pre' WHEN month >= DATE '2023-09-01' THEN 'post' ELSE 'excluded' END era
 FROM totals
), flags AS (
 SELECT *, complaints >= $minimum AND peer_complaints >= $minimum AND known>0 AND peer_known>0 AND complete_month AND era<>'excluded' eligible_month,
 -- Integer cross-products make the inclusive one-percentage-point boundary exact.
 known>0 AND peer_known>0 AND era<>'excluded'
 AND untimely::HUGEINT*peer_known*100 >= peer_untimely::HUGEINT*known*100 + known::HUGEINT*peer_known elevated
 FROM monthly
), rolling AS (
 SELECT *, count(*) OVER w months_in_window, count(*) FILTER(WHERE eligible_month) OVER w eligible_months,
 min(era) OVER w first_era, max(era) OVER w last_era,
 count(*) FILTER(WHERE elevated AND eligible_month) OVER w elevated_months,
 sum(complaints) FILTER(WHERE era<>'excluded') OVER w window_complaints,
 sum(known) FILTER(WHERE era<>'excluded') OVER w window_known,
 sum(untimely) FILTER(WHERE era<>'excluded') OVER w window_no,
 sum(peer_known) FILTER(WHERE era<>'excluded') OVER w window_peer_known,
 sum(peer_untimely) FILTER(WHERE era<>'excluded') OVER w window_peer_no,
 lag(issue_share) OVER history previous_share, lag(era) OVER history previous_era,
 lag(complete_month) OVER history previous_complete
 FROM flags
 WINDOW history AS (PARTITION BY company,product,issue ORDER BY month),
 w AS (PARTITION BY company,product,issue ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
), evaluated AS (
 SELECT *, months_in_window=3 AND eligible_months=3 AND first_era=last_era window_eligible,
 100*(window_no::DOUBLE/nullif(window_known,0)-window_peer_no::DOUBLE/nullif(window_peer_known,0)) pooled_excess_pp,
 CASE WHEN complete_month AND previous_complete AND era=previous_era AND era<>'excluded' THEN previous_share END prior_issue_share,
 CASE WHEN complete_month AND previous_complete AND era=previous_era AND era<>'excluded' THEN 100*(issue_share-previous_share) END issue_share_change_pp
 FROM rolling
), candidates AS (
 SELECT *,
  window_no::HUGEINT*window_peer_known-window_peer_no::HUGEINT*window_known excess_numerator,
  window_known::HUGEINT*window_peer_known excess_denominator
 FROM evaluated WHERE window_eligible AND elevated_months>=2
), reduced AS (
 SELECT *,
  excess_numerator // gcd(abs(excess_numerator),excess_denominator) excess_num,
  excess_denominator // gcd(abs(excess_numerator),excess_denominator) excess_den
 FROM candidates
), rank_keys AS (
 SELECT DISTINCT month,elevated_months,excess_num,excess_den,window_no,window_complaints
 FROM reduced
), ordered_keys AS (
 -- Count distinct strictly better tuples; exact rational comparison preserves ties.
 SELECT a.*,1+count(b.month) priority_rank
 FROM rank_keys a LEFT JOIN rank_keys b ON a.month=b.month AND (
  b.elevated_months>a.elevated_months OR
  (b.elevated_months=a.elevated_months AND (
   b.excess_num*a.excess_den>a.excess_num*b.excess_den OR
   (b.excess_num*a.excess_den=a.excess_num*b.excess_den AND (
    b.window_no>a.window_no OR
    (b.window_no=a.window_no AND b.window_complaints>a.window_complaints)
   ))
  ))
 )
 GROUP BY ALL
), priorities AS (
 SELECT r.company,r.product,r.issue,r.month,k.priority_rank
 FROM reduced r JOIN ordered_keys k USING
  (month,elevated_months,excess_num,excess_den,window_no,window_complaints)
)
SELECT e.*, e.issue IS NULL OR e.issue='' issue_missing,
 struct_pack(is_null := e.issue IS NULL, raw_label := e.issue) issue_key,
 window_eligible AND elevated_months>=2 persistent, p.priority_rank
FROM evaluated e LEFT JOIN priorities p
 ON e.company IS NOT DISTINCT FROM p.company AND e.product IS NOT DISTINCT FROM p.product
 AND e.issue IS NOT DISTINCT FROM p.issue AND e.month=p.month
WHERE ($issues IS NULL OR list_contains(CAST($issues AS VARCHAR[]),e.issue) OR (e.issue IS NULL AND list_contains(list_transform(CAST($issues AS VARCHAR[]),lambda x: x IS NULL),true)))
ORDER BY e.month, p.priority_rank NULLS LAST, e.company NULLS FIRST,e.product NULLS FIRST,e.issue NULLS FIRST;
