import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from live_edge_plan import arithmetic_case, focused_cases


class EnginePlanTests(unittest.TestCase):
    def test_arithmetic_oracle_contains_exact_ties_and_negative_gaps(self):
        case = arithmetic_case()
        self.assertEqual(len(case['expectedRows']), 104)
        self.assertEqual([row['comparison'] for row in case['expectedRows'][:4]], [0, 0, 0, -1])
        self.assertEqual(case['keyColumns'], ['id'])
        self.assertNotIn('RANKX', case['query'])

    def test_focused_expectations_come_from_sql_plan(self):
        monthly = [dict(month=f'2025-{month:02d}-01', complaints=100, known=90, untimely=10,
            peer_complaints=100, peer_known=90, peer_untimely=0, elevated=True,
            window_no=30, window_known=270, window_peer_no=0, window_peer_known=270,
            persistent=True, priority_rank=2, elevated_months=3, pooled_excess_pp=100/9)
            for month in (10, 11, 12)]
        plan = dict(focal=dict(selection_key=17, diagnostics=monthly),
            cases=[dict(id='all_100', expected=dict(eligible_windows=9, qualifying_windows=3,
                qualifying_segments=2, stable_windows=0))])
        cases = {case['id']: case for case in focused_cases(plan)}
        self.assertEqual(cases['focal_window']['expected']['rank'], 2)
        self.assertEqual(cases['focal_keeps_population_counts']['expected']['eligible'], 9)
        self.assertEqual(cases['focal_sensitivity_100']['expected']['result'], 'Qualifies')
        self.assertEqual(cases['focal_sensitivity_200']['expected']['result'], 'Does not qualify')
        self.assertEqual(len(cases['focal_monthly']['expectedRows']), 3)
        self.assertIsNone(cases['ambiguous_minimum_unavailable']['expected']['qualifying'])


if __name__ == '__main__':
    unittest.main()
