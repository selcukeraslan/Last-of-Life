"""P2: haber kaynaklarının önbelleği ve etkili haberli/habersiz A/B testi."""
import tempfile
import urllib.parse
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app import db
from app.model.snapshots import news_impact_report
from app.scrapers import news


class NewsImpactTests(unittest.TestCase):
    def test_news_effect_requires_enough_affected_matches(self):
        better = [([.8, .1, .1], [.5, .3, .2], 0)] * 20
        self.assertEqual(news_impact_report(better)["verdict"], "insufficient_data")
        convincing = news_impact_report(better * 6)
        self.assertEqual(convincing["verdict"], "news_improves")
        self.assertLess(convincing["interval95"][1], 0)

    def test_news_harms_or_inconclusive(self):
        worse = [([.4, .3, .3], [.8, .1, .1], 0)] * 120
        self.assertEqual(news_impact_report(worse)["verdict"], "news_hurts")
        self.assertEqual(news_impact_report([])["n"], 0)


class NewsCacheTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for p in (patch.object(db, "DATABASE_URL", None),
                  patch.object(db, "DB_PATH", Path(tmp.name) / "news.db")):
            p.start()
            self.addCleanup(p.stop)
        db.init_db()

    def test_distant_match_cached_but_urgent_refetched(self):
        now = datetime.now(timezone.utc)
        with db.session() as conn:
            for mid, league, home, away, offset in (
                ("a", "eng.1", "Arsenal", "Chelsea", 72),
                ("b", "tur.1", "Galatasaray", "Fenerbahce", 2),
            ):
                conn.execute(
                    "INSERT INTO matches(id,league,kickoff,home,away,completed) "
                    "VALUES(?,?,?,?,?,0)",
                    (mid, league, (now + timedelta(hours=offset)).isoformat(), home, away))
        calls = []
        def fake_fetch(team, lang, **_):
            calls.append(team)
            return []
        with patch.object(news, "fetch_team_news", side_effect=fake_fetch), \
                patch.object(news.time, "sleep"), db.session() as conn:
            self.assertEqual(news.sync_news(conn), 0)
            self.assertEqual(len(calls), 4)
            self.assertEqual(news.sync_news(conn), 0)
            self.assertEqual(len(calls), 4)  # hiçbir takım gereksiz tekrar sorgulanmadı
            conn.execute("UPDATE meta SET value=? WHERE key LIKE 'news_poll_%'",
                         ((now - timedelta(hours=2)).isoformat(),))
            self.assertEqual(news.sync_news(conn), 0)
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) n FROM meta WHERE key LIKE 'news_poll_%'"
            ).fetchone()["n"], 4)
        self.assertEqual(len(calls), 6)  # yalnız maçına 24 saat kalan iki takım yenilendi


def rss(*titles):
    items = "".join(f"<item><title>{t} - Kaynak</title><link>https://n/{i}</link><source>Kaynak</source>"
                    f"<pubDate>Fri, 13 Nov 2026 10:00:00 GMT</pubDate></item>" for i, t in enumerate(titles))
    return f"<rss><channel>{items}</channel></rss>".encode()


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TeamDisambiguationTests(unittest.TestCase):
    """Aynı adlı yabancı kulüplerin (Athletic Club Sjdr, New York Athletic Club…) haberleri sızmasın."""

    def test_english_query_scopes_to_league_and_adds_media_alias(self):
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(news.rss_url("Athletic Club", "en", "esp.1")).query)["q"][0]
        self.assertTrue(q.startswith('("Athletic Club" OR "Athletic Bilbao") football (LaLiga OR "La Liga" OR Spain OR Spanish)'), q)
        plain = urllib.parse.parse_qs(urllib.parse.urlsplit(news.rss_url("Arsenal", "en", "eng.1")).query)["q"][0]
        self.assertTrue(plain.startswith('"Arsenal" football ("Premier League" OR England OR English)'), plain)
        self.assertIn('"Arsenal" football when:', urllib.parse.parse_qs(urllib.parse.urlsplit(news.rss_url("Arsenal", "en")).query)["q"][0])
        tr = urllib.parse.parse_qs(urllib.parse.urlsplit(news.rss_url("Besiktas", "tr", "tur.1")).query)["q"][0]
        self.assertTrue(tr.startswith('"Beşiktaş" when:'), tr)

    def test_title_filter_uses_word_boundaries_in_english_but_allows_turkish_suffixes(self):
        self.assertTrue(news.mentions(news.fold("Athletic Club vs Barcelona"), ["athletic"], "en"))
        self.assertFalse(news.mentions(news.fold("Oakland Athletics sign new pitcher"), ["athletic"], "en"))
        self.assertFalse(news.mentions(news.fold("Nicely done by Marseille"), ["nice"], "en"))
        self.assertTrue(news.mentions(news.fold("Galatasaraylı yıldız sakatlandı"), ["galatasaray"], "tr"))
        self.assertTrue(news.mentions(news.fold("Beşiktaş'ın kadrosu açıklandı"), ["besiktas"], "tr"))

    def test_fetch_keeps_alias_titles_and_classifies_them_as_own_team(self):
        body = rss("Osasuna vs Athletic Bilbao: Confirmed Lineups", "Athletic Club playmaker Sancet out with injury",
                   "Oakland Athletics trade news", "Standings - La Liga")
        with patch.object(news.urllib.request, "urlopen", return_value=FakeResponse(body)) as opened:
            items = news.fetch_team_news("Athletic Club", "en", league="esp.1")
        self.assertIn("Athletic+Bilbao", opened.call_args[0][0].full_url)
        self.assertEqual([i["title"] for i in items], ["Osasuna vs Athletic Bilbao: Confirmed Lineups", "Athletic Club playmaker Sancet out with injury"])
        self.assertEqual(items[1]["injury"], 1)


if __name__ == "__main__":
    unittest.main()
