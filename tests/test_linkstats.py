import math
import unittest

from telemetri.linkstats import (Rolling, SeqLossTracker, fspl_db, link_grade, link_margin_db,
                                 percentile, sik_raw_to_dbm, sik_snr_db)


class SeqLossTest(unittest.TestCase):
    def test_no_loss(self):
        t = SeqLossTracker()
        for s in range(300):
            self.assertEqual(t.update(1, 1, s % 256), 0)
        self.assertEqual(t.lost, 0)
        self.assertEqual(t.loss_pct, 0.0)

    def test_gap_and_wrap(self):
        t = SeqLossTracker()
        t.update(1, 1, 250)
        self.assertEqual(t.update(1, 1, 253), 2)   # 251, 252 lost
        self.assertEqual(t.update(1, 1, 1), 3)     # 254, 255, 0 lost across wrap
        self.assertEqual(t.lost, 5)
        self.assertAlmostEqual(t.loss_pct, 100 * 5 / 8)

    def test_components_are_independent(self):
        t = SeqLossTracker()
        t.update(1, 1, 10)
        t.update(51, 68, 200)  # radio injects RADIO_STATUS with its own seq
        self.assertEqual(t.update(1, 1, 11), 0)
        self.assertEqual(t.update(51, 68, 201), 0)

    def test_reset_not_counted_as_loss(self):
        t = SeqLossTracker()
        t.update(1, 1, 10)
        self.assertEqual(t.update(1, 1, 200), 0)   # reboot / stream restart
        self.assertEqual(t.resets, 1)


class SikTest(unittest.TestCase):
    def test_conversion(self):
        self.assertAlmostEqual(sik_raw_to_dbm(0), -127.0)
        self.assertAlmostEqual(sik_raw_to_dbm(190), -27.0)
        self.assertAlmostEqual(sik_snr_db(150, 55), 50.0)

    def test_grade(self):
        self.assertEqual(link_grade(35), "EXCELLENT")
        self.assertEqual(link_grade(12), "MARGINAL")
        self.assertEqual(link_grade(3), "CRITICAL")


class StatsTest(unittest.TestCase):
    def test_percentile(self):
        self.assertEqual(percentile([1, 2, 3, 4, 5], 50), 3)
        self.assertAlmostEqual(percentile([1, 2, 3, 4], 50), 2.5)
        self.assertTrue(math.isnan(percentile([], 50)))

    def test_rolling_window(self):
        r = Rolling(3)
        for v in (1, 2, 3, 10):
            r.add(v)
        self.assertEqual(len(r), 3)
        self.assertAlmostEqual(r.mean, 5.0)
        self.assertEqual(r.min, 2)


class LinkBudgetTest(unittest.TestCase):
    def test_fspl_reference(self):
        # 1 km @ 433 MHz ~ 85.2 dB, 915 MHz ~ 91.7 dB
        self.assertAlmostEqual(fspl_db(1, 433), 85.17, places=1)
        self.assertAlmostEqual(fspl_db(1, 915) - fspl_db(1, 433), 6.5, places=1)

    def test_margin(self):
        m = link_margin_db(20, 2.15, 2.15, 1, 1, 433, -108)
        self.assertAlmostEqual(m, 20 + 4.3 - 1 - 85.17 + 108, places=1)


if __name__ == "__main__":
    unittest.main()
