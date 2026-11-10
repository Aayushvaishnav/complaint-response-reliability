"""Behavior checks for the independent raw-CSV product audit."""
from io import StringIO
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_product_findings import product_counts


class ProductReferenceTests(unittest.TestCase):
    def test_exact_flags_and_raw_product_keys(self):
        text = 'Product,Timely response?\nP,Yes\nP,No\nP, Yes\nP,\n,No\nP ,Yes\n'
        result = product_counts(StringIO(text))
        self.assertEqual(result['P'], dict(complaints=4, timely=1, untimely=1, known=2, unknown=2))
        self.assertEqual(result['']['untimely'], 1)
        self.assertEqual(result['P ']['complaints'], 1)
        self.assertEqual(sum(r['complaints'] for r in result.values()), 6)

    def test_empty_and_missing_schema(self):
        self.assertEqual(product_counts(StringIO('Product,Timely response?\n')), {})
        with self.assertRaises(ValueError):
            product_counts(StringIO('Product,Wrong\nP,Yes\n'))


if __name__ == '__main__':
    unittest.main()
