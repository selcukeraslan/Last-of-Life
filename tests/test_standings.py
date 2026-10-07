import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app import db, main
from app.config import LEAGUES, league_aliases, resolve_league
from app.model import engine


class StandingsLeagueResolutionTests(unittest.TestCase):
    def test_every_configured_league_identifier_resolves(self):
        for league in LEAGUES:
            with self.subTest(league=league):
                self.assertEqual(resolve_league(league), league)

    def test_every_configured_slug_name_and_alias_resolves(self):
        for league in LEAGUES:
            for alias in league_aliases(league):
                with self.subTest(league=league, alias=alias):
                    self.assertEqual(resolve_league(alias), league)

    def test_standings_uses_canonical_id_for_every_configured_league(self):
        model = SimpleNamespace(elo=SimpleNamespace(get=lambda _team: 1567.5),
                                table=[{"team": "Test FC", "pos": 1, "pts": 3}])
        for league in LEAGUES:
            with self.subTest(league=league), patch.object(main.engine, "get_model", return_value=model) as get_model:
                rows = main.standings(league)
                get_model.assert_called_once_with(league)
                self.assertEqual(rows, [{"team": "Test FC", "pos": 1, "pts": 3, "elo": 1568}])

    def test_unknown_league_returns_not_found_without_loading_a_model(self):
        with patch.object(main.engine, "get_model") as get_model:
            with self.assertRaises(HTTPException) as raised:
                main.standings("not-a-league")
        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail, "Bilinmeyen lig")
        get_model.assert_not_called()


class PortugueseStandingsSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path_patch = patch.object(db, "DB_PATH", Path(self.tmp.name) / "standings.db")
        self.db_path_patch.start()
        db.init_db()
        with db.session() as conn:
            for match in [
                ("por-1", "por.1", "2026-08-10T15:00:00+00:00", "Benfica", "Porto", 2, 0),
                ("por-2", "por.1", "2026-08-17T15:00:00+00:00", "Sporting CP", "Benfica", 1, 1),
                ("eng-1", "eng.1", "2026-08-10T15:00:00+00:00", "Other FC", "Another FC", 5, 0),
            ]:
                conn.execute(
                    "INSERT INTO matches(id, league, kickoff, home, away, home_goals, away_goals, completed) "
                    "VALUES(?, ?, ?, ?, ?, ?, ?, 1)", match)
        engine.invalidate()
        self.addCleanup(engine.invalidate)
        self.addCleanup(self.db_path_patch.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_portugal_alias_reads_canonical_por_dot_1_match_data(self):
        rows = main.standings("Portuguese Primeira Liga")
        table = {row["team"]: row for row in rows}

        self.assertEqual(table["Benfica"]["pts"], 4)
        self.assertEqual(table["Benfica"]["p"], 2)
        self.assertEqual(table["Porto"]["pts"], 0)
        self.assertNotIn("Other FC", table)


if __name__ == "__main__":
    unittest.main()
