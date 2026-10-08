import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

from fastapi import HTTPException

from app import seo
from tests.test_pwa import asgi_get

M = {"id": "401888280", "home": "Galatasaray", "away": "Kasımpaşa", "league_name": "Süper Lig",
     "kickoff": "2026-10-09T17:00:00+00:00", "iddaa_odds": {"1": 1.5},
     "markets": {"1": {"p": .6, "suggested": 1.6}, "X": {"p": .22, "suggested": 4.5}, "2": {"p": .18, "suggested": 5.5},
                 "Ü2.5": {"p": .6, "suggested": 1.7}, "KG Var": {"p": .55, "suggested": 1.8}},
     "scores": [{"score": "2-0", "p": .12}]}


def fake_match(mid):
    if mid != M["id"]:
        raise HTTPException(404, "Maç bulunamadı")
    return M


class SeoTest(unittest.TestCase):
    def test_page(self):
        with patch("app.main.match", fake_match), patch("app.ops.cached", lambda k, b: b()):
            status, headers, body = asgi_get("/mac/galatasaray-kasimpasa-401888280")
        html = body.decode()
        self.assertEqual(status, 200)
        self.assertIn("s-maxage", headers["cache-control"])
        for s in ("Galatasaray - Kasımpaşa tahmini, oranlar (9 Ekim 2026)", 'rel="canonical"', 'property="og:title"',
                  'name="twitter:card"', '"SportsEvent"', "18+", "Detaylı analiz", "name=\"description\""):
            self.assertIn(s, html)

    def test_missing(self):
        with patch("app.main.match", fake_match):
            self.assertEqual(asgi_get("/mac/x-y-999")[0], 404)

    def test_sitemap_and_robots(self):
        with patch("app.main._upcoming", lambda lg, d: [M]), patch("app.ops.cached", lambda k, b: b()):
            status, _, body = asgi_get("/sitemap.xml")
        self.assertEqual(status, 200)
        locs = [e.text for e in ET.fromstring(body).iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
        self.assertIn(seo.SITE + "/mac/galatasaray-kasimpasa-401888280", locs)
        self.assertIn(b"Sitemap:", asgi_get("/robots.txt")[2])


class FrontendLinkTest(unittest.TestCase):
    def test_app_opens_shared_match(self):
        from app.config import STATIC_DIR
        js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn('get("match")', js)
        self.assertIn("openMatch(sharedMatch)", js)
