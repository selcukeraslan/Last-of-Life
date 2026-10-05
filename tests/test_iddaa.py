import unittest

from app.scrapers.iddaa import match_event, normalize_team, parse_event


class IddaaScraperTests(unittest.TestCase):
    def test_team_aliases_and_turkish_characters(self):
        self.assertEqual(normalize_team("İstanbul Başakşehir FK"), "basaksehir")
        self.assertEqual(normalize_team("Rams Basaksehir"), "basaksehir")
        self.assertEqual(normalize_team("Çaykur Rizespor"), "rizespor")
        self.assertEqual(normalize_team("Manchester City FC"), "manchester city")

    def test_required_markets_are_parsed(self):
        raw = {
            "i": 123,
            "ci": 584,
            "d": 1791220000,
            "hn": "Fenerbahçe",
            "an": "Beşiktaş",
            "m": [
                {"t": 1, "st": 1, "s": 1, "o": [
                    {"no": 1, "odd": 1.91}, {"no": 2, "odd": 3.2}, {"no": 3, "odd": 3.8}]},
                {"t": 2, "st": 92, "s": 1, "o": [
                    {"no": 1, "odd": 1.18}, {"no": 2, "odd": 1.25}, {"no": 3, "odd": 1.55}]},
                {"t": 2, "st": 101, "s": 1, "sov": "1.5", "o": [
                    {"no": 1, "odd": 2.4}, {"no": 2, "odd": 1.3}]},
                {"t": 2, "st": 101, "s": 1, "sov": "2.5", "o": [
                    {"no": 1, "odd": 1.75}, {"no": 2, "odd": 1.85}]},
                {"t": 2, "st": 101, "s": 1, "sov": "3.5", "o": [
                    {"no": 1, "odd": 1.35}, {"no": 2, "odd": 2.3}]},
                {"t": 2, "st": 89, "s": 1, "o": [
                    {"no": 1, "odd": 1.64}, {"no": 2, "odd": 1.77}]},
            ],
        }
        event = parse_event(raw)
        self.assertEqual(event["league"], "tur.1")
        self.assertEqual(event["odds"], {
            "1": 1.91, "X": 3.2, "2": 3.8,
            "1X": 1.18, "12": 1.25, "X2": 1.55,
            "A1.5": 2.4, "Ü1.5": 1.3,
            "A2.5": 1.75, "Ü2.5": 1.85,
            "A3.5": 1.35, "Ü3.5": 2.3,
            "KG Var": 1.64, "KG Yok": 1.77,
        })

    def test_event_matches_fixture_by_alias_and_time(self):
        event = {
            "league": "eng.1", "home": "Man City", "away": "Wolves",
            "kickoff": "2026-10-17T14:00:00+00:00",
        }
        fixtures = [
            {"id": "espn-1", "league": "eng.1", "home": "Manchester City",
             "away": "Wolverhampton Wanderers", "kickoff": "2026-10-17T14:00Z"},
            {"id": "espn-2", "league": "eng.1", "home": "Manchester United",
             "away": "Everton", "kickoff": "2026-10-17T14:00Z"},
        ]
        matched, score = match_event(event, fixtures)
        self.assertEqual(matched["id"], "espn-1")
        self.assertGreater(score, 0.95)


if __name__ == "__main__":
    unittest.main()
