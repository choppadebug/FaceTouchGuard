"""Run with: python -m unittest -v tests.test_alert_logic"""
import unittest
from alerts.alert_logic import AlertTimeline


class AlertTimelineTests(unittest.TestCase):
    def setUp(self):
        self.a = AlertTimeline()

    def test_timeline_exact_thresholds(self):
        # New event confirmed after 0.35 seconds; onset=0.
        self.assertEqual(self.a.update(.35, 1, True, True).stage, 1)
        self.assertEqual(self.a.update(1.49, 1, True, True).stage, 1)
        self.assertEqual(self.a.update(1.50, 1, True, True).stage, 2)
        self.assertEqual(self.a.update(2.99, 1, True, True).stage, 2)
        self.assertEqual(self.a.update(3.0, 1, True, True).stage, 3)

    def test_alert_stops_on_first_no_proximity_even_during_release_hysteresis(self):
        self.a.update(.35, 1, True, True)
        result = self.a.update(.40, 1, True, False)
        self.assertEqual(result.stage, 0)

    def test_no_replay_after_tracking_flicker(self):
        first = self.a.update(.35, 1, True, True)
        self.assertTrue(first.entered_stage)
        self.a.update(.40, 1, True, False)
        resumed = self.a.update(.45, 1, True, True)
        self.assertEqual(resumed.stage, 1)
        self.assertFalse(resumed.entered_stage)

    def test_new_event_restarts_alerts(self):
        self.a.update(.35, 1, True, True)
        self.a.update(1.5, 1, True, True)
        self.a.update(2.0, 1, False, False)
        new = self.a.update(10.0, 2, True, True)
        self.assertEqual(new.stage, 1)
        self.assertTrue(new.entered_stage)

    def test_does_not_alert_before_detector_confirms_contact(self):
        self.assertEqual(self.a.update(.1, 0, False, True).stage, 0)


if __name__ == "__main__":
    unittest.main()
