import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app import db
from app.db import get_meta
from app.scrapers import tff


def row(date, time, home, away, mac, hs="", as_="", hid=74, aid=3623):
    return f"""<tr class="haftaninMaclariTr">
      <td><b><span id="x_lblTarih">{date}</span><span id="x_lblSaat">{time}</span></b></td>
      <td><a href="Default.aspx?pageId=28&kulupID={hid}" id="x_A2"><span id="x_Label4">{home}</span></a></td>
      <td><b><a href="Default.aspx?pageId=29&macId={mac}" id="x_A3"><span id="x_Label5">{hs}</span>
          -
          <span id="x_Label6">{as_}</span></a></td>
      <td><a href="Default.aspx?pageId=28&kulupID={aid}" id="x_A5"><span id="x_Label1">{away}</span></a></td>
      <td><a href="Default.aspx?pageId=29&macId={mac}"><span>Detaylar</span></a></td></tr>"""


def page(week, total, rows):
    tabs = "".join(f'<li><a class="x">{n}.Hafta</a></li>' for n in range(1, total + 1))
    selected = (f'<li><a disabled="disabled" class="aspNetDisabled TRcolor"><span class="wrap">'
                f'<span class="innerWrap">{week}.Hafta</span></span></a></li>')
    return f"<html>{selected}<table>{''.join(rows)}</table>{tabs}</html>"


NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


class ParseTests(unittest.TestCase):
    def test_parses_week_page(self):
        body = page(8, 38, [
            row("18.09.2026", "20:00", "BANDIRMA SPOR", "EMİNEVİM ÜMRANİYESPOR", 318163, "0", "1", 130, 3661),
            row("09.10.2026", "17:00", "EKENLER BETON SİVASSPOR", "ORFA YAPI PENDİKSPOR FUTBOL A.Ş.", 318178),
        ])
        r = tff.parse_page(body, "tur.2", now=NOW)
        self.assertEqual((r["week"], r["total_weeks"]), (8, 38))
        played, upcoming = r["matches"]
        self.assertEqual(played["id"], "tff-318163")
        self.assertEqual((played["home"], played["away"]), ("Bandırmaspor", "Ümraniyespor"))
        self.assertEqual(played["kickoff"], "2026-09-18T17:00Z")  # TSİ (UTC+3) -> UTC
        self.assertEqual((played["home_goals"], played["away_goals"], played["completed"]), (0, 1, 1))
        self.assertEqual((played["home_id"], played["away_id"]), ("tff-130", "tff-3661"))
        self.assertEqual((upcoming["home"], upcoming["away"]), ("Sivasspor", "Pendikspor"))
        self.assertEqual((upcoming["completed"], upcoming["home_goals"]), (0, None))

    def test_live_score_is_not_completed(self):
        body = page(9, 38, [row("06.10.2026", "14:30", "A", "B", 1, "1", "0")])  # 11:30Z, 30 dk önce başladı
        match = tff.parse_page(body, "tur.2", now=NOW)["matches"][0]
        self.assertEqual((match["completed"], match["home_goals"]), (0, None))

    def test_unknown_club_name_is_cleaned(self):
        self.assertEqual(tff.club_name("1", "YENİ SPONSOR ÖRNEKSPOR FUTBOL A.Ş."), "Yeni Sponsor Örnekspor")


class SyncTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for p in (patch.object(db, "DB_PATH", Path(tmp.name) / "t.db"), patch.object(db, "DATABASE_URL", None)):
            p.start()
            self.addCleanup(p.stop)
        db.init_db()
        self.fetched = []

    def fake_fetch(self, current, total, completed_weeks):
        def fetch(league, week=None, **kw):
            week = week or current
            self.fetched.append(week)
            done = week <= completed_weeks
            body = page(week, total, [row("01.09.2026", "20:00", "A", "B", 1000 + week,
                                          "1" if done else "", "0" if done else "")])
            return tff.parse_page(body, league, now=NOW)
        return fetch

    def test_full_sync_skips_finished_weeks_next_time(self):
        with patch.object(tff, "fetch_week", self.fake_fetch(5, 38, 4)), patch.object(tff, "REQUEST_DELAY_SEC", 0):
            with db.session() as conn:
                n = tff.sync_league(conn, "tur.2")
            self.assertEqual(self.fetched, [5, 1, 2, 3, 4, 6, 7, 8])  # güncel hafta + geçmiş haftalar + 3 hafta ileri
            self.assertEqual(n, 8)
            with db.session() as conn:
                self.assertEqual(get_meta(conn, "tff_done_tur.2"), "5")
                self.assertEqual(conn.execute("SELECT COUNT(*) n FROM matches WHERE league='tur.2'").fetchone()["n"], 8)
            self.fetched.clear()
            with db.session() as conn:
                tff.sync_league(conn, "tur.2")
        self.assertEqual(self.fetched, [5, 6, 7, 8])  # biten haftalar tekrar çekilmedi

    def test_quick_sync_fetches_current_and_previous_week(self):
        with patch.object(tff, "fetch_week", self.fake_fetch(9, 38, 8)):
            with db.session() as conn:
                count, ok = tff.sync_recent(conn, "tur.2")
        self.assertTrue(ok)
        self.assertEqual((count, self.fetched), (2, [9, 8]))

    def test_quick_sync_reports_failure(self):
        with patch.object(tff, "fetch_week", side_effect=RuntimeError("down")), db.session() as conn:
            self.assertEqual(tff.sync_recent(conn, "tur.2"), (0, False))


if __name__ == "__main__":
    unittest.main()
