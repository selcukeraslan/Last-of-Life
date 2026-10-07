import unittest

from app.config import LEAGUES, is_cup
from app.scrapers.iddaa import COMPETITION_IDS, match_event, parse_event, small_league_key, team_similarity


def event(league, home, away, kickoff="2026-10-10T14:30:00+00:00"):
    return {"league": league, "home": home, "away": away, "kickoff": kickoff}


def fixture(league, home, away, kickoff="2026-10-10T14:30Z"):
    return {"id": "1", "league": league, "home": home, "away": away, "kickoff": kickoff}


class NewLeagueTests(unittest.TestCase):
    def test_every_mapped_competition_points_to_a_configured_league(self):
        self.assertTrue(set(COMPETITION_IDS.values()) <= set(LEAGUES))
        for league in ("tur.2", "ned.1", "por.1", "uefa.champions", "uefa.europa"):
            self.assertIn(league, COMPETITION_IDS.values())
        self.assertEqual(COMPETITION_IDS[1980], "tur.2")
        self.assertEqual(COMPETITION_IDS[322], "ned.1")
        self.assertEqual(COMPETITION_IDS[566], "por.1")

    def test_config_flags(self):
        self.assertTrue(is_cup("uefa.champions") and is_cup("uefa.europa"))
        self.assertFalse(is_cup("tur.2"))
        self.assertEqual(LEAGUES["tur.2"]["source"], "tff")

    def test_outright_records_without_teams_are_skipped(self):
        self.assertIsNone(parse_event({"i": 1, "ci": 126, "d": 1791220000, "m": []}))
        self.assertEqual(parse_event({"i": 2, "ci": 126, "d": 1791220000, "hn": "A", "an": "B", "m": []})["league"],
                         "uefa.champions")

    def test_unknown_competition_is_small_league_with_country_and_name(self):
        parsed = parse_event({"i": 3, "ci": 99999, "d": 1791220000, "hn": "A", "an": "B",
                              "countryName": "Faroe Islands", "competitionName": "Premier League"})
        self.assertEqual(parsed["league"], small_league_key("Faroe Islands", "Premier League"))
        self.assertEqual((parsed["country"], parsed["league_name"]), ("Faroe Islands", "Premier League"))

    def test_event_without_competition_name_keeps_unique_competition_id(self):
        parsed = parse_event({"i": 4, "ci": 98765, "d": 1791220000, "hn": "A", "an": "B"})
        self.assertIn("98765", parsed["league"])

    def test_dutch_and_portuguese_names_match_espn_names(self):
        pairs = [("Ajax", "Ajax Amsterdam"), ("Feyenoord", "Feyenoord Rotterdam"), ("PSV", "PSV Eindhoven"),
                 ("Zwolle", "PEC Zwolle"), ("Sporting Lizbon", "Sporting CP"), ("Sporting de Braga", "Braga"),
                 ("Nacional da Madeira", "C.D. Nacional"), ("Estoril-Praia", "Estoril"),
                 ("Marítimo", "Maritimo"), ("Vitoria de Guimaraes", "Vitória de Guimaraes")]
        for iddaa_name, espn_name in pairs:
            self.assertGreaterEqual(team_similarity(iddaa_name, espn_name), 0.9, (iddaa_name, espn_name))

    def test_european_cup_names_match(self):
        pairs = [("Bodo Glimt", "Bodo/Glimt"), ("FC Red Bull Salzburg", "RB Salzburg"),
                 ("Slavia Prag", "Slavia Prague"), ("B. Dortmund", "Borussia Dortmund"),
                 ("Union Saint Gilloise", "Union St.-Gilloise"), ("Kopenhag", "F.C. København"),
                 ("Inter", "Internazionale"), ("Olympiakos", "Olympiacos"), ("Lillestrøm", "Lillestrom")]
        for iddaa_name, espn_name in pairs:
            self.assertGreaterEqual(team_similarity(iddaa_name, espn_name), 0.9, (iddaa_name, espn_name))

    def test_tff_fixture_matches_iddaa_event(self):
        fixtures = [fixture("tur.2", "Sivasspor", "Pendikspor", "2026-10-09T14:00Z"),
                    fixture("tur.2", "Bodrum FK", "Ankara Keçiörengücü", "2026-10-09T14:00Z")]
        found, score = match_event(event("tur.2", "Sivasspor", "Pendikspor", "2026-10-09T14:00:00+00:00"), fixtures)
        self.assertEqual(found["home"], "Sivasspor")
        self.assertGreater(score, 0.9)

    def test_cup_event_only_matches_same_competition(self):
        fixtures = [fixture("uefa.champions", "Ajax Amsterdam", "Galatasaray"),
                    fixture("ned.1", "Ajax Amsterdam", "Galatasaray")]
        found, _ = match_event(event("uefa.champions", "Ajax", "Galatasaray"), fixtures)
        self.assertEqual(found["league"], "uefa.champions")


if __name__ == "__main__":
    unittest.main()
