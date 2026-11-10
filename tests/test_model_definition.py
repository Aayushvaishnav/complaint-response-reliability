"""Offline blueprint contract checks; live DAX and refresh acceptance are separate."""
import json
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from model_definition import build_definition


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.definition = build_definition('C:/inputs')
        self.tables = {t['name']: t for t in self.definition['tableDefinitions']}
        self.measures = {m['name']: m for m in self.definition['measureDefinitions']}

    def test_schema_and_explicit_foundation_boundary(self):
        self.assertEqual(self.definition['status'], 'foundation_only')
        self.assertEqual(set(self.tables), {'Complaint Cohorts', 'Date', 'Company', 'Product',
                         'Issue', 'Geography', 'Review Minimum', 'Sensitivity Minimum',
                         'Review Window', 'Review Selection'})
        self.assertEqual(set(self.measures), {'Complaint Count', 'Timely Yes Count',
                         'Untimely No Count', 'Known Flag Count', 'Unknown Flag Count',
                         'Timely Response Rate', 'Untimely Share', 'Unknown Flag Rate',
                         'Valid Routing Count', 'Invalid Routing Count', 'Median Routing Days',
                         'Monthly Issue Share', 'Peer Complaint Count', 'Peer Known Count',
                         'Peer No Count', 'Peer Untimely Share'})
        for measure in self.measures.values():
            self.assertTrue(measure['description'])
            self.assertTrue(measure['formatString'])
            self.assertTrue(measure['displayFolder'])
            self.assertFalse(measure['isHidden'])
            self.assertNotIn('dataType', measure)
            self.assertNotRegex(measure['expression'], r'(?i)RANKX|0\.1[05]|202[345]|SELECTEDVALUE')
        self.assertEqual(len({m['expression'] for m in self.measures.values()}), 16)

    def test_types_mapping_and_hidden_statistics(self):
        expected = {'Complaint Cohorts': 11, 'Date': 7, 'Company': 5, 'Product': 5,
                    'Issue': 5, 'Geography': 5, 'Review Minimum': 1,
                    'Sensitivity Minimum': 1, 'Review Window': 3, 'Review Selection': 15}
        m_types = {'String': 'type text', 'Int64': 'Int64.Type', 'DateTime': 'type date',
                   'Boolean': 'type logical'}
        for name, table in self.tables.items():
            columns = table['columns']
            self.assertEqual(len(columns), expected[name])
            self.assertEqual(len({c['name'] for c in columns}), len(columns))
            self.assertEqual(len({c['sourceColumn'] for c in columns}), len(columns))
            expression = table['mExpression']
            self.assertEqual(table['partitionName'], name)
            self.assertEqual(table['mode'], 'Import')
            self.assertNotIn('partitions', table)
            self.assertIn('Parquet.Document(File.Contents(#"Source Folder" & "/', expression)
            self.assertIn('Table.TransformColumnTypes', expression)
            for c in columns:
                self.assertIn('{"' + c['sourceColumn'] + '", ' + m_types[c['dataType']] + '}', expression)
                self.assertEqual(c['summarizeBy'], 'None')
                self.assertNotIn('isKey', c)
                self.assertTrue(c['description'])
                if name == 'Complaint Cohorts' or c['name'].endswith((' Key', ' Raw', ' Missingness')):
                    self.assertTrue(c['isHidden'])
        date_columns = {c['name']: c for c in self.tables['Date']['columns']}
        self.assertEqual(date_columns['Month Label']['sortByColumn'], 'Month Order')
        self.assertEqual(date_columns['Date']['dataType'], 'DateTime')
        selector = {c['name']: c for c in self.tables['Review Selection']['columns']}
        for name in ('Company', 'Product', 'Issue', 'Window End'):
            self.assertFalse(selector[name]['isHidden'])
        for name in ('Company', 'Product', 'Issue'):
            self.assertEqual(selector[name]['groupByColumns'], [name + ' Key'])
        for dimension in ('Company', 'Product', 'Issue', 'Geography'):
            label = 'State' if dimension == 'Geography' else dimension
            column = next(c for c in self.tables[dimension]['columns'] if c['name'] == label)
            self.assertEqual(column['groupByColumns'], [dimension + ' Key'])

    def test_relationships_and_no_utility_filter_leak(self):
        relationships = self.definition['relationshipDefinitions']
        self.assertEqual(len(relationships), 5)
        self.assertEqual({r['toTable'] for r in relationships}, {'Date', 'Company', 'Product', 'Issue', 'Geography'})
        for r in relationships:
            self.assertEqual(r['fromTable'], 'Complaint Cohorts')
            self.assertEqual((r['fromCardinality'], r['toCardinality']), ('Many', 'One'))
            self.assertEqual(r['crossFilteringBehavior'], 'OneDirection')
            self.assertTrue(r['isActive'])
            sides = [{c['name']: c for c in self.tables[r[side + 'Table']]['columns']}[r[side + 'Column']]
                     for side in ('from', 'to')]
            self.assertEqual(sides[0]['dataType'], sides[1]['dataType'])

    def test_parameter_only_owns_folder_and_escapes_m_literal(self):
        folder = 'C:/a"b/#(lf)/inputs'
        blueprint = build_definition(folder)
        self.assertIn('C:/a""b/#(#)(lf)/inputs', blueprint['parameterDefinition']['expression'])
        self.assertNotIn('C:/', json.dumps(blueprint['tableDefinitions']))
        self.assertTrue(blueprint['modelDefinition']['discourageImplicitMeasures'])
        for invalid in ('', ' ', None, 3):
            with self.assertRaises(ValueError):
                build_definition(invalid)
        blueprint['tableDefinitions'].clear()
        self.assertEqual(len(build_definition(folder)['tableDefinitions']), 10)

    def test_peer_filter_scope_and_undefined_rates(self):
        for name, base in [('Peer Complaint Count', 'Complaint Count'),
                           ('Peer Known Count', 'Known Flag Count'), ('Peer No Count', 'Untimely No Count')]:
            expression = self.measures[name]['expression']
            self.assertEqual(re.findall(r'REMOVEFILTERS\((.*?)\)', expression), ["'Issue'"])
            self.assertTrue(expression.endswith(' - [' + base + ']'))
        for name in ('Timely Response Rate', 'Untimely Share', 'Unknown Flag Rate',
                     'Monthly Issue Share', 'Peer Untimely Share'):
            expression = self.measures[name]['expression']
            self.assertTrue(expression.startswith('DIVIDE('))
            self.assertNotIn(', 0)', expression)
        for name in ('Complaint Count', 'Timely Yes Count', 'Untimely No Count', 'Unknown Flag Count'):
            self.assertIn('COALESCE(SUM(', self.measures[name]['expression'])
            self.assertNotIn('COUNTROWS', self.measures[name]['expression'])

    def test_weighted_median_uses_frequency_cumulative_and_both_positions(self):
        expression = self.measures['Median Routing Days']['expression']
        for fragment in ('SUM(\'Complaint Cohorts\'[Complaint Rows])', 'SUMX(_bins, [__frequency])',
                         '_total + 1', '_total + 2', '__cumulative', '<= _day',
                         '_lower + _upper', '_total > 0', 'BLANK()', 'KEEPFILTERS', 'NOT ISBLANK'):
            self.assertIn(fragment, expression)
        self.assertNotRegex(expression, r'\bMEDIANX?\(')
        # Independent frequency algorithm fixtures expose unweighted-bin and even-middle errors
        for bins, expected in [([], None), ([(0, 1)], 0), ([(1, 3), (9, 1)], 1),
                               ([(1, 1), (9, 1)], 5), ([(0, 2), (7, 3)], 7)]:
            total = sum(n for _, n in bins)
            positions = ((total + 1) // 2, (total + 2) // 2)
            values = []
            for position in positions:
                cumulative = 0
                for day, count in bins:
                    cumulative += count
                    if cumulative >= position:
                        values.append(day)
                        break
            result = sum(values) / 2 if total else None
            self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
