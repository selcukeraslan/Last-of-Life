import unittest

from app.model.predict import CONF_LABELS, confidence


class ConfidenceRuleTest(unittest.TestCase):
    def test_reported_inconsistency_is_gone(self):
        # Eski hesapta %57 "Yüksek", %64 "Düşük" çıkabiliyordu; aynı veri kapsamında artık imkânsız.
        self.assertLessEqual(confidence(0.57, 18)["level"], confidence(0.64, 18)["level"])
        self.assertEqual(confidence(0.64, 18)["label"], "Yüksek")
        self.assertEqual(confidence(0.57, 18)["label"], "Orta")

    def test_monotone_in_probability_and_data(self):
        ps = [i / 200 for i in range(80, 140)]  # %40–70
        ns = [0, 3, 6, 8, 10, 12, 15, 20]
        for n in ns:
            levels = [confidence(p, n)["level"] for p in ps]
            self.assertEqual(levels, sorted(levels), f"n={n}")
        for p in ps:
            levels = [confidence(p, n)["level"] for n in ns]
            self.assertEqual(levels, sorted(levels), f"p={p}")

    def test_thresholds(self):
        self.assertEqual(confidence(0.5599, 20)["label"], "Düşük")
        self.assertEqual(confidence(0.56, 20)["label"], "Orta")
        self.assertEqual(confidence(0.62, 20)["label"], "Yüksek")

    def test_data_caps_label(self):
        self.assertEqual(confidence(0.66, 10)["label"], "Orta")
        self.assertEqual(confidence(0.66, 4)["label"], "Düşük")
        self.assertIn("veri az", confidence(0.66, 4)["reason"])

    def test_label_matches_level(self):
        c = confidence(0.6, 15)
        self.assertEqual(CONF_LABELS[c["level"]], c["label"])


if __name__ == "__main__":
    unittest.main()
