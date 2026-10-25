import unittest
from datetime import datetime, timedelta, timezone

from app.model.ratings import parse_ts
from app.model.predict import confidence
from app.news_intel import classify, summarize


def row(title, hours_ago, team="Galatasaray", now=None):
    now = now or datetime(2026, 10, 14, tzinfo=timezone.utc)
    return {"title": title, "link": title, "source": "x", "published": (now - timedelta(hours=hours_ago)).isoformat()}


class ClassifyTest(unittest.TestCase):
    def test_injury_and_suspension(self):
        self.assertEqual(classify("Osimhen sakatlığı nedeniyle oynayamayacak", "Galatasaray")["category"], "out")
        self.assertEqual(classify("Ethan Mbappé banned for three games after red card", "Lille")["category"], "suspended")

    def test_return_from_injury(self):
        self.assertEqual(classify("Goalkeeper returns to Coventry City after injury setback", "Coventry City")["category"], "return")

    def test_opponent_news_is_ignored(self):
        c = classify("Hansi Flick's options if Raphinha is ruled out for Barcelona's Getafe clash", "Getafe")
        self.assertEqual(c["category"], "ignored")

    def test_transfer_and_preview_are_ignored(self):
        self.assertEqual(classify("Harry Kane close to new contract", "Bayern Munich")["category"], "ignored")
        self.assertEqual(classify("Lyon vs Marseille live game updates", "Lyon")["category"], "ignored")

    def test_women_and_reserves_are_ignored(self):
        self.assertEqual(classify("Eintracht Frankfurt (W) Frauen-Bundesliga stats", "Eintracht Frankfurt")["category"], "ignored")


class SummarizeTest(unittest.TestCase):
    def test_no_news_is_neutral(self):
        s = summarize("Galatasaray", [], datetime(2026, 10, 14, tzinfo=timezone.utc), parse_ts)
        self.assertEqual((s["att"], s["opp"], s["relevant"]), (0.0, 0.0, 0))

    def test_same_absence_counted_once(self):
        rows = [row("Osimhen sakatlık son durum", 2), row("Osimhen sakatlığı ile ilgili yeni gelişme", 5)]
        s = summarize("Galatasaray", rows, datetime(2026, 10, 14, tzinfo=timezone.utc), parse_ts)
        self.assertEqual(s["counts"].get("out"), 1)

    def test_effect_is_capped(self):
        rows = [row(f"Oyuncu{i} sakatlık nedeniyle oynayamayacak", i + 1) for i in range(10)]
        s = summarize("Galatasaray", rows, datetime(2026, 10, 14, tzinfo=timezone.utc), parse_ts)
        self.assertGreaterEqual(s["att"], -0.12)

    def test_return_cancels_earlier_absence(self):
        rows = [row("Osimhen sakatlık nedeniyle oynayamayacak", 48), row("Osimhen sahalara döndü", 2)]
        s = summarize("Galatasaray", rows, datetime(2026, 10, 14, tzinfo=timezone.utc), parse_ts)
        self.assertEqual(s["absences"], 0)


class MitigationTest(unittest.TestCase):
    def test_league_return_is_not_player_return(self):
        self.assertNotEqual(classify("Premier League return date confirmed for Everton", "Everton")["category"], "return")

    def test_per_player_effect_about_three_percent(self):
        s = summarize("Galatasaray", [row("Osimhen sakatlık nedeniyle oynayamayacak", 2)],
                      datetime(2026, 10, 14, tzinfo=timezone.utc), parse_ts)
        self.assertAlmostEqual(s["att_pct"], -3.4, places=1)


class NewsConfidenceTest(unittest.TestCase):
    def test_no_news_does_not_override_probability_and_history(self):
        c = confidence(0.8, 20, news_teams=0)
        self.assertEqual(c, confidence(0.8, 20, news_teams=2))
        self.assertEqual(confidence(.8, 3, news_teams=0)["confidence_label"], "Düşük")

    def test_one_team_news_does_not_cap_the_label(self):
        self.assertEqual(confidence(0.8, 20, news_teams=1)["confidence_label"], "Yüksek")

    def test_both_teams_news_keeps_level(self):
        self.assertEqual(confidence(0.8, 20, news_teams=2)["confidence_label"], "Yüksek")


if __name__ == "__main__":
    unittest.main()
