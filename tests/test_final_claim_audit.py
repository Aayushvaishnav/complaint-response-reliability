import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_final_claims import monthly_screen


class FocalAuditTests(unittest.TestCase):
    def test_peer_volume_controls_eligible_monthly_elevation(self):
        monthly = [dict(segment_complaints=n, segment_known=n, segment_no=no,
                        peer_complaints=p, peer_known=p, peer_no=pn)
                   for n, no, p, pn in [(340, 121, 129, 36), (245, 168, 131, 81), (387, 301, 192, 136)]]
        for minimum in (50, 100):
            self.assertEqual(monthly_screen(monthly, minimum),
                             dict(volume_eligible=True, elevated_months=3, persistent=True))
        self.assertEqual(monthly_screen(monthly, 200),
                         dict(volume_eligible=False, elevated_months=0, persistent=False))

    def test_empty_and_unknown_denominators_cannot_qualify(self):
        self.assertEqual(monthly_screen([], 100),
                         dict(volume_eligible=False, elevated_months=0, persistent=False))
        month = dict(segment_complaints=200, segment_known=0, segment_no=0,
                     peer_complaints=200, peer_known=200, peer_no=0)
        self.assertFalse(monthly_screen([month] * 3, 100)['persistent'])


if __name__ == '__main__':
    unittest.main()
