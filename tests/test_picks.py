import unittest

from app.model import blend, calibration, picks, predict as P


def ch(market, p, odds):
    return {"market": market, "p": p, "odds": odds}


class ScoreTest(unittest.TestCase):
    def test_low_probability_high_odds_is_penalised(self):
        self.assertGreater(picks.score(0.60, 1.7, "1"), picks.score(0.30, 4.5, "Ü3.5"))

    def test_edge_is_capped(self):
        capped = picks.score(0.6, 3.0, "") - picks.score(0.6, 2.0, "")
        self.assertLess(capped, 0.0)  # sınırlı EV bonusu + yüksek oran cezası

    def test_min_probability_and_families(self):
        self.assertIsNone(picks.best_choice([ch("1", 0.5, 2.0)]))
        self.assertIsNone(picks.best_choice([ch("İY 1", 0.9, 2.0), ch("Korner Ü9.5", 0.9, 2.0)]))
        self.assertIsNone(picks.best_choice([ch("Ü1.5", 0.76, 1.4)]))  # bilgisiz pazar
        self.assertEqual(picks.best_choice([ch("Ü1.5", 0.76, 1.4)], allow_trivial=True)["market"], "Ü1.5")
        self.assertIsNone(picks.family("Handikap 1 1"))  # 1X'in kopyası


class DiversityTest(unittest.TestCase):
    def test_no_family_dominates_when_alternatives_exist(self):
        entries = [({"id": i}, [ch("1", 0.62, 1.7), ch("Ü2.5", 0.60, 1.8)]) for i in range(10)]
        chosen = picks.assign(entries)
        n_1 = sum(c["market"] == "1" for _, c in chosen)
        self.assertEqual(len(chosen), 10)
        self.assertTrue(3 <= n_1 <= 7)  # iki pazar da kullanılır

    def test_soft_cap_still_picks_when_only_option(self):
        entries = [({"id": i}, [ch("1", 0.62, 1.7)]) for i in range(6)]
        self.assertEqual(len(picks.assign(entries)), 6)


class CalibrationTest(unittest.TestCase):
    def test_pairs_stay_complementary(self):
        mk = {"KG Var": P.odds(0.62), "KG Yok": P.odds(0.38), "1": P.odds(0.5)}
        out = calibration.calibrate_markets(mk)
        self.assertAlmostEqual(out["KG Var"]["p"] + out["KG Yok"]["p"], 1, places=3)
        self.assertLess(out["KG Var"]["p"], 0.62)  # KG olasılıkları aşırıydı, büzülür
        self.assertEqual(out["1"], mk["1"])


class BestPickTest(unittest.TestCase):
    def test_uses_iddaa_odds_and_threshold(self):
        mk = {"1": P.odds(0.58), "X": P.odds(0.25), "2": P.odds(0.17), "1X": P.odds(0.83), "X2": P.odds(0.42)}
        pick = P.best_pick(mk, {"1": 1.9})
        self.assertEqual(pick["market"], "1")
        self.assertIsNone(P.best_pick({"1": P.odds(0.40), "X": P.odds(0.30), "2": P.odds(0.30)}))


class ExtraBlendTest(unittest.TestCase):
    def test_handicap_shrinks_toward_market(self):
        extra = {f"Handikap -1 {r}": {"p": p, "fair": 1 / p, "suggested": 1 / p, "model_available": True}
                 for r, p in zip("1X2", (0.60, 0.20, 0.20))}
        odds = {"Handikap -1 1": 2.4, "Handikap -1 X": 3.6, "Handikap -1 2": 2.6}
        out = blend.blend_extra_markets(extra, odds, 0.5)
        self.assertLess(out["Handikap -1 1"]["p"], 0.60)
        self.assertIn("market_p", out["Handikap -1 1"])
        self.assertAlmostEqual(sum(out[f"Handikap -1 {r}"]["p"] for r in "1X2"), 1, places=2)
        self.assertEqual(blend.blend_extra_markets(extra, {}, 0.5), extra)


if __name__ == "__main__":
    unittest.main()
