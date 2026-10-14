import unittest

from app.model.predict import CONF_CUTS, CONF_LABELS, confidence, confidence_label


class ConfidenceRuleTest(unittest.TestCase):
    def test_pick_probability_orders_label(self):
        # Eski hesapta %57 "Yüksek", %64 "Düşük" çıkabiliyordu; aynı veri kapsamında artık imkânsız.
        self.assertLessEqual(confidence(0.57, 18)["confidence"], confidence(0.64, 18)["confidence"])
        self.assertEqual(confidence(0.64, 18)["confidence_label"], "Yüksek")
        self.assertEqual(confidence(0.57, 18)["confidence_label"], "Orta")

    def test_monotone_in_probability_and_data(self):
        ps = [i / 200 for i in range(80, 140)]  # %40–70
        ns = [0, 3, 6, 8, 10, 12, 15, 20]
        for n in ns:
            vals = [confidence(p, n)["confidence"] for p in ps]
            self.assertEqual(vals, sorted(vals), f"n={n}")
        for p in ps:
            vals = [confidence(p, n)["confidence"] for n in ns]
            self.assertEqual(vals, sorted(vals), f"p={p}")

    def test_thresholds(self):
        self.assertEqual(confidence(0.5599, 20)["confidence_label"], "Düşük")
        self.assertEqual(confidence(0.56, 20)["confidence_label"], "Orta")
        self.assertEqual(confidence(0.62, 20)["confidence_label"], "Yüksek")

    def test_data_caps_label(self):
        self.assertEqual(confidence(0.66, 10)["confidence_label"], "Orta")
        self.assertEqual(confidence(0.66, 4)["confidence_label"], "Düşük")
        self.assertEqual(confidence(0.66, 12)["confidence_label"], "Yüksek")
        self.assertIn("veri az", confidence(0.66, 4)["confidence_reason"])

    def test_label_always_derived_from_float(self):
        for p in (0.4, 0.55, 0.559, 0.56, 0.6, 0.62, 0.7):
            for n in (0, 5, 8, 11, 12, 20):
                c = confidence(p, n)
                self.assertEqual(c["confidence_label"], confidence_label(c["confidence"]))
                self.assertEqual(CONF_LABELS[(c["confidence"] >= CONF_CUTS[0]) + (c["confidence"] >= CONF_CUTS[1])],
                                 c["confidence_label"])

    def test_no_pick(self):
        c = confidence(None, 20)
        self.assertEqual((c["confidence"], c["confidence_label"]), (0.0, "Düşük"))
        self.assertTrue(c["confidence_reason"])


if __name__ == "__main__":
    unittest.main()
