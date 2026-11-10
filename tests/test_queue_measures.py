import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from priority_measures import build_priority_measures
from queue_measures import build_queue_measures, QUEUE_FIELDS
from live_native_queue_plan import native_query


class QueueDisplayTests(unittest.TestCase):
    def test_queue_fields_project_only_qualifying_sparse_rows(self):
        diagnostics = {m['name']: m for m in build_priority_measures()}
        definitions = build_queue_measures()
        self.assertEqual(len(definitions), len(QUEUE_FIELDS))
        self.assertFalse({m['name'] for m in definitions} & diagnostics.keys())
        for base, measure in zip(QUEUE_FIELDS, definitions):
            self.assertEqual(measure['name'], 'Queue ' + base)
            self.assertIn('VAR _row = FILTER(_qualified, _single && [__key] == _key)', measure['expression'])
            self.assertNotIn(f'[{base}]', measure['expression'])
            self.assertNotIn('GENERATE(', measure['expression'])
            self.assertEqual(measure['formatString'], diagnostics[base]['formatString'])
            self.assertEqual(measure['expression'].count('('), measure['expression'].count(')'))
        definitions[0]['name'] = 'mutated'
        self.assertEqual(build_queue_measures()[0]['name'], 'Queue Elevated Months')

    def test_native_query_has_full_identity_grouping_without_measure_filter(self):
        query = native_query(["'Review Minimum'[Minimum] = 100"], define=True)
        self.assertIn("'Review Selection'[Selection Key]", query)
        self.assertIn("'Review Selection'[Company Key]", query)
        self.assertIn("'Review Selection'[Company]", query)
        self.assertIn('[Queue Window No Count]', query)
        self.assertNotIn('__ValueFilterDM', query)
        self.assertNotIn('NOT ISBLANK([rank])', query)
        self.assertNotIn('TOPN', query)


if __name__ == '__main__':
    unittest.main()
