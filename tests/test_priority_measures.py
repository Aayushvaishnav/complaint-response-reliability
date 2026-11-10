"""Offline generator contract tests; these do not parse or execute DAX."""
import re
import sys
import unittest
from pathlib import Path
from fractions import Fraction

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from priority_measures import build_priority_measures
from model_definition import build_definition
from rank_arithmetic import ArithmeticPlan, SOURCE_LIMIT


class PriorityDefinitionsTests(unittest.TestCase):
    def setUp(self):
        self.definitions = build_priority_measures()
        self.measures = {m['name']: m['expression'] for m in self.definitions}

    def test_fresh_mcp_payload_and_no_foundation_collisions(self):
        self.assertEqual(len(self.definitions), len(self.measures))
        foundation = build_definition('C:/model-input')
        self.assertFalse(set(self.measures) & {m['name'] for m in foundation['measureDefinitions']})
        self.definitions[0]['name'] = 'mutated'
        self.assertEqual(build_priority_measures()[0]['name'], 'Selected Review Minimum')
        for definition in self.definitions:
            self.assertEqual(definition['tableName'], 'Complaint Cohorts')
            for key in ('description', 'displayFolder', 'formatString', 'expression'):
                self.assertTrue(definition[key])

    def test_all_qualified_column_references_exist(self):
        schema = {t['name']: {c['name'] for c in t['columns']}
                  for t in build_definition('C:/model-input')['tableDefinitions']}
        for expression in self.measures.values():
            for table, column in re.findall(r"'([^']+)'\[([^]]+)\]", expression):
                self.assertIn(column, schema[table])

    def test_review_context_string_is_terminated(self):
        context = self.measures['Review Context']
        self.assertTrue(context.rstrip().endswith('"'))
        self.assertEqual(context.count('"') % 2, 0)
        self.assertIn('_endCount = _allEndCount', context)

    def test_generated_expressions_have_balanced_delimiters(self):
        for name, expression in self.measures.items():
            without_strings = re.sub(r'"(?:[^"]|"")*"', '', expression)
            self.assertEqual(without_strings.count('('), without_strings.count(')'), name)

    def test_selection_minimum_and_scope_contracts(self):
        minimum = self.measures['Selected Review Minimum']
        self.assertIn("NOT ISFILTERED('Review Minimum')", minimum)
        self.assertIn('HASONEVALUE', minimum)
        self.assertIn('BLANK()', minimum)
        for name in ('Eligible Window Count', 'Qualifying Window Count', 'Qualifying Segment Count', 'Stable Window Count'):
            expression = self.measures[name]
            self.assertIn("ALL('Review Selection')", expression)
            self.assertNotIn('_focusKey', expression)
            self.assertIn("ALLSELECTED('Date')", expression)
        for name in ('Review Reason', 'Sensitivity Result', 'Priority Rank'):
            self.assertIn("HASONEVALUE('Review Selection'[Selection Key])", self.measures[name])
        self.assertNotRegex('\n'.join(self.measures.values()), r"SELECTEDVALUE\('Review Selection'\[(Company|Product|Issue)\]\)")

    def test_exact_arithmetic_is_embedded_and_bounded(self):
        rank = self.measures['Priority Rank']
        self.assertEqual(rank.count(ArithmeticPlan().dax()), 2)
        self.assertNotIn('RANKX', rank)
        self.assertIn('[__key] < _rightKey', rank)
        self.assertIn('[__end] = _targetEnd', rank)
        # Monthly threshold uses at most 100*T²/4; exact Int64 and binary64
        bound = 100 * (SOURCE_LIMIT // 2) * (SOURCE_LIMIT - SOURCE_LIMIT // 2)
        self.assertLess(bound, 2**53)
        self.assertLess(bound, 2**63)
        for no, known, peer_no, peer_known in [(1,100,0,100), (0,100,0,100), (2,100,1,100), (1,101,0,100)]:
            integer_rule = 100 * (no * peer_known - peer_no * known) >= known * peer_known
            self.assertEqual(integer_rule, Fraction(no,known)-Fraction(peer_no,peer_known) >= Fraction(1,100))

    def test_window_and_sensitivity_contracts(self):
        expression = self.measures['Review Reason']
        for fragment in ('GENERATESERIES(0, 2)', 'EDATE(_end, -2)', 'COUNTROWS(_monthDates) = DAY(EOMONTH',
                         '_end < DATE(2023,8,1) || _start >= DATE(2023,9,1)',
                         "KEEPFILTERS(TREATAS({_company}, 'Company'[Company Key]))",
                         "REMOVEFILTERS('Issue')", '100 * ([__fn] * [__pk] - [__pn] * [__fk])'):
            self.assertIn(fragment, expression)
        self.assertIn('{50,100,200}', self.measures['Passing Minima'])
        self.assertIn("HASONEVALUE('Sensitivity Minimum'[Minimum])", self.measures['Sensitivity Result'])
        self.assertIn('EDATE(_month, -1)', self.measures['Issue Share Change pp'])
        self.assertIn('COUNTROWS(_priorDates) = DAY(EOMONTH', self.measures['Issue Share Change pp'])
        self.assertIn('MAXX(_row, [__peerKnown]) > 0', self.measures['Pooled Gap pp'])


if __name__ == '__main__':
    unittest.main()
