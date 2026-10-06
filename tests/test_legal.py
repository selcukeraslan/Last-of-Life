import unittest

from app.config import STATIC_DIR

DISCLAIMER = "18+ · Tahminler garanti değildir, yatırım tavsiyesi değildir. Sorumlu oynayın."


class LegalNoticeTest(unittest.TestCase):
    def setUp(self):
        self.html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    def test_footer_has_disclaimer(self):
        footer = self.html.split("<footer", 1)[1].split("</footer>", 1)[0]
        self.assertIn(DISCLAIMER, footer)

    def test_assets_linked_and_present(self):
        self.assertIn('href="/static/legal.css"', self.html)
        self.assertIn('src="/static/legal.js"', self.html)
        self.assertLess(self.html.index("legal.js"), self.html.index("app.js"))  # onay kutusu önce gelsin
        for name in ("legal.css", "legal.js"):
            self.assertTrue((STATIC_DIR / name).is_file())

    def test_age_gate_and_coupon_note(self):
        js = (STATIC_DIR / "legal.js").read_text(encoding="utf-8")
        self.assertIn("18 yaşından büyüğüm", js)
        self.assertIn("localStorage", js)
        self.assertIn(".coupon-card", js)
        self.assertIn("Tahminler garanti değildir", js)


if __name__ == "__main__":
    unittest.main()
