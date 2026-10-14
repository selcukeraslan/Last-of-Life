import unittest

from app.model.extra_markets import for_match
from app.value_bets import collect
from app.model.coupons import _choices


class ExtraMarketsTest(unittest.TestCase):
    def test_first_half_and_half_full_probabilities_are_modelled(self):
        markets = for_match(1.4, 1.0, {"İY A1.5": 1.9, "İY Ü1.5": 1.9,
                                     "Handikap -1 1": 2.0, "Handikap -1 X": 3.0,
                                     "Handikap -1 2": 4.0})
        self.assertAlmostEqual(sum(markets[f"İY {r}"]["p"] for r in ("1", "X", "2")), 1, places=3)
        self.assertAlmostEqual(sum(markets[f"İY/MS {a}/{b}"]["p"] for a in ("1", "X", "2")
                                   for b in ("1", "X", "2")), 1, places=3)
        self.assertAlmostEqual(sum(markets[f"Handikap -1 {r}"]["p"] for r in ("1", "X", "2")), 1, places=3)
        self.assertAlmostEqual(markets["İY A1.5"]["p"] + markets["İY Ü1.5"]["p"], 1, places=3)
        integer_line = for_match(1.4, 1.0, {"İY A1": 1.9, "İY Ü1": 1.9})
        self.assertLess(integer_line["İY A1"]["p"] + integer_line["İY Ü1"]["p"], 1)
        self.assertGreater(integer_line["İY A1"]["p"] + integer_line["İY Ü1"]["p"], 0.5)

    def test_negative_handicap_is_applied_to_home_team(self):
        # Canlı bülten: 1X2 "1" 1.13 favorisinde çizgi -2 ve "Handikap -2 1" ~2.2 oranlı.
        # Çizgi EV sahibine eklenir: ev 2 gol geriden başlar, "1" = ev 3+ farkla kazanır.
        markets = for_match(2.6, 0.5, {"Handikap -2 1": 2.2, "Handikap -2 X": 4.0, "Handikap -2 2": 2.1})
        self.assertAlmostEqual(sum(markets[f"Handikap -2 {r}"]["p"] for r in ("1", "X", "2")), 1, places=3)
        self.assertLess(markets["Handikap -2 1"]["p"], 0.6)  # eskiden ~%95 (işaret hatası)
        self.assertGreater(markets["Handikap -2 1"]["p"], 0.25)
        self.assertGreater(markets["Handikap -2 2"]["p"], markets["Handikap -2 X"]["p"])

    def test_positive_handicap_helps_home_team(self):
        markets = for_match(0.8, 1.6, {"Handikap 1 1": 1.9, "Handikap 1 X": 3.5, "Handikap 1 2": 2.5})
        self.assertGreater(markets["Handikap 1 1"]["p"], markets["Handikap 1 2"]["p"] - 0.2)

    def test_corner_and_card_quotes_have_no_model_probability(self):
        markets = for_match(1.4, 1.0, {"Korner A9.5": 1.9, "Kart Ü4.5": 2.1})
        self.assertIsNone(markets["Korner A9.5"]["p"])
        self.assertIsNone(markets["Kart Ü4.5"]["suggested"])
        prediction = {"id": "1", "league": "eng.1", "kickoff": "2026-10-17T14:00Z",
                      "home": "H", "away": "A", "lambda_home": 1.4, "lambda_away": 1.0,
                      "markets": {}, "extra_markets": markets}
        odds = {"1": {"odds": {"Korner A9.5": 2.5, "Kart Ü4.5": 2.5}}}
        self.assertEqual(collect([prediction], odds)["items"], [])
        choices = _choices(prediction, odds["1"]["odds"])
        self.assertFalse(any(c["market"].startswith(("Korner ", "Kart ")) for c in choices))


if __name__ == "__main__":
    unittest.main()
