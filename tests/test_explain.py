import unittest

from app import explain


def game(venue, result, gf=1, ga=0):
    return {"venue": venue, "result": result, "gf": gf, "ga": ga, "opponent": "X", "date": "2025-01-01"}


def item(market, **over):
    base = {
        "id": "1", "home": "Ev", "away": "Dep", "pick": {"market": market, "p": 0.6}, "confidence_label": "Yüksek",
        "iddaa_odds": {"1": 1.8, "2": 2.1},
        "factors": {
            "form": {"home": [game("E", "G")] * 4 + [game("D", "M", 0, 1)], "away": [game("D", "M", 0, 2)] * 3 + [game("E", "G")],
                     "home_ppg": 2.2, "away_ppg": 0.8},
            "news": {"home": {"absences": 0}, "away": {"absences": 2}},
            "h2h": [{"home": "Ev", "away": "Dep", "score": "2-0"}, {"home": "Dep", "away": "Ev", "score": "0-1"}],
        },
    }
    base.update(over)
    return base


class ExplainTest(unittest.TestCase):
    def test_home_win_summary(self):
        s = explain.summarize(item("1"))
        self.assertEqual((s["headline"], s["title"], s["odds"], s["level"]), ("MS 1", "Ev sahibi kazanır", 1.8, 3))
        self.assertIn("Ev son 5 maçta 4 galibiyet aldı.", s["reason"])
        self.assertIn("2 oyuncu eksik", s["reason"])
        self.assertLessEqual(s["reason"].count(". "), 2)

    def test_away_win_uses_away_team(self):
        s = explain.summarize(item("2", confidence_label="Orta"))
        self.assertEqual((s["headline"], s["title"], s["level"]), ("MS 2", "Deplasman kazanır", 2))

    def test_totals_and_btts_titles(self):
        self.assertEqual(explain.headline("Ü2.5"), "2.5 Üst")
        self.assertEqual(explain.title("Ü2.5"), "3 veya daha fazla gol")
        self.assertEqual(explain.title("A2.5"), "En fazla 2 gol")
        self.assertIn("ortalama", explain.summarize(item("Ü2.5"))["reason"])

    def test_other_markets_get_neutral_reason(self):
        for market in ("12", "Ev 0.5Ü", "Dep 0.5Ü"):
            reason = explain.summarize(item(market))["reason"]
            self.assertEqual(reason, explain._FALLBACK)
            self.assertNotIn("atamadı", reason)

    def test_btts_no_text(self):
        self.assertIn("atamadı", explain.summarize(item("KG Yok"))["reason"])

    def test_no_pick(self):
        s = explain.summarize(item("1", pick=None))
        self.assertIsNone(s["market"])

    def test_missing_factors_falls_back(self):
        s = explain.summarize(item("1", factors=None))
        self.assertTrue(s["reason"])

    def test_no_jargon_in_reason(self):
        text = explain.summarize(item("1"))["reason"].lower()
        for word in ("ev ", "xg", "elo", "lambda", "kelly", "örtük", "adil oran"):
            if word == "ev ":
                continue
            self.assertNotIn(word, text)


if __name__ == "__main__":
    unittest.main()
