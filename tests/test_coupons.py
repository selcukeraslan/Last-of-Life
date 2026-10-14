import math
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app import db
from app.main import coupons as coupons_endpoint, picks as picks_endpoint
from app.model import coupons as cp
from app.model.coupons import (_choices, _coupon, select_banko, select_banko_alternatives,
                               select_surprise, select_surprise_alternatives, select_small_league,
                               small_league_recommendation)


def pred(mid, markets, kickoff="2026-10-17T14:00Z", league="eng.1"):
    return {"id": mid, "league": league, "kickoff": kickoff, "home": f"H{mid}", "away": f"A{mid}",
            "markets": {m: {"p": p, "suggested": s, "fair": round(1 / p, 2)} for m, (p, s) in markets.items()}}


def entry(mid, markets, iddaa=None, **kw):
    p = pred(mid, markets, **kw)
    return p, _choices(p, iddaa or {})


class OddsSourceTest(unittest.TestCase):
    def test_iddaa_odds_preferred_with_claude_fallback(self):
        p = pred(1, {"1": (0.6, 1.60), "X": (0.25, 4.0)})
        by_market = {c["market"]: c for c in _choices(p, {"1": 1.85})}
        self.assertEqual((by_market["1"]["odds"], by_market["1"]["odds_source"]), (1.85, "iddaa"))
        self.assertEqual(by_market["1"]["claude_odds"], 1.60)
        self.assertEqual((by_market["X"]["odds"], by_market["X"]["odds_source"]), (4.0, "claude"))
        self.assertIsNone(by_market["X"]["iddaa_odds"])

    def test_coupon_totals_and_source(self):
        picks = [{"odds": 2.0, "p": 0.8, "odds_source": "iddaa"}, {"odds": 1.5, "p": 0.75, "odds_source": "claude"}]
        c = _coupon("banko", picks, "n")
        self.assertEqual((c["total_odds"], c["total_probability"]), (3.0, 0.6))
        self.assertEqual((c["odds_source"], c["iddaa_picks"]), ("karışık", 1))
        self.assertEqual(_coupon("banko", picks[:1], "n")["odds_source"], "iddaa")
        self.assertIsNone(_coupon("banko", [], "n")["odds_source"])


class BankoTest(unittest.TestCase):
    def test_one_pick_per_match_and_rules(self):
        entries = [entry(1, {"1": (0.80, 1.30), "Ü1.5": (0.78, 1.30)}),
                   entry(2, {"1X": (0.90, 1.18)}),
                   entry(3, {"2": (0.76, 1.40)}),
                   entry(4, {"1": (0.70, 1.50)})]  # p < %75
        picks = select_banko(entries)
        self.assertEqual([x["id"] for x in picks], [2, 1, 3])
        self.assertEqual(len({x["id"] for x in picks}), len(picks))
        self.assertGreaterEqual(math.prod(x["p"] for x in picks), 0.5)

    def test_total_probability_floor_drops_third_pick(self):
        picks = select_banko([entry(i, {"1": (0.76, 1.40)}) for i in (1, 2, 3)])  # .76^3 = .44
        self.assertEqual(len(picks), 2)

    def test_single_match_is_not_a_coupon(self):
        self.assertEqual(select_banko([entry(1, {"1": (0.9, 1.20)})]), [])

    def test_min_odds_uses_iddaa_odds_when_available(self):
        # Claude oranı 1.20 yeterli ama iddaa 1.08 -> seçim dışı; iki maç kalmazsa kupon yok.
        entries = [entry(1, {"1": (0.8, 1.30)}, {"1": 1.08}), entry(2, {"1": (0.8, 1.30)})]
        self.assertEqual(select_banko(entries), [])

    def test_empty_day(self):
        self.assertEqual(select_banko([]), [])


class SurpriseTest(unittest.TestCase):
    def test_total_odds_floor_unique_matches_and_size(self):
        entries = [entry(i, {"X": (0.30, 3.0), "2": (0.28, 3.4), "Ü2.5": (0.45, 2.2)}) for i in range(1, 8)]
        picks = select_surprise(entries)
        self.assertTrue(3 <= len(picks) <= 5)
        self.assertEqual(len({x["id"] for x in picks}), len(picks))
        self.assertGreaterEqual(math.prod(x["odds"] for x in picks), 15)

    def test_never_returns_coupon_below_15(self):
        entries = [entry(i, {"X": (0.4, 1.7)}) for i in range(1, 6)]  # 1.7^5 = 14.2
        self.assertEqual(select_surprise(entries), [])

    def test_fewer_than_three_matches(self):
        self.assertEqual(select_surprise([entry(i, {"X": (0.3, 3.0)}) for i in (1, 2)]), [])

    def test_ev_uses_iddaa_odds(self):
        entries = [entry(1, {"X": (0.30, 3.3)}, {"X": 4.0})] + [entry(i, {"X": (0.30, 3.3)}) for i in (2, 3, 4)]
        by_id = {x["id"]: x for x in select_surprise(entries)}
        self.assertEqual(by_id[1]["odds_source"], "iddaa")
        self.assertAlmostEqual(by_id[1]["value"], 0.30 * 4.0 - 1, places=4)
        self.assertTrue(all(x["odds_source"] == "claude" for i, x in by_id.items() if i != 1))

    def test_prefers_likelier_combo_not_lottery_odds(self):
        entries = [entry(i, {"2": (0.50, 3.6)}) for i in range(1, 9)]  # 3 maç = 46.7 oran; 5 maç gereksiz
        picks = select_surprise(entries)
        self.assertEqual(len(picks), 3)

    def test_probability_band(self):
        entries = [entry(i, {"X": (0.10, 9.0), "2": (0.65, 1.6)}) for i in range(1, 6)]
        self.assertEqual(select_surprise(entries), [])  # X p<0.30, 2 p>0.62
        entries = [entry(i, {"1": (0.40, 2.6)}) for i in range(1, 6)]
        self.assertTrue(select_surprise(entries))  # tüm pazar aileleri izinli, bant içinde


class CouponAlternativesTest(unittest.TestCase):
    def test_banko_alternatives_are_unique_and_span_main_leagues(self):
        entries = [entry(i, {"1": (0.82 - i * 0.01, 1.35)}, league=league)
                   for i, league in enumerate(("eng.1", "tur.1", "esp.1", "ger.1"), 1)]
        small = entry(9, {"1": (0.95, 1.5)}, league="small:country:league")
        small[0]["small_league"] = True
        alternatives = select_banko_alternatives(entries + [small])
        signatures = [frozenset(p["id"] for p in coupon) for coupon in alternatives]
        self.assertGreaterEqual(len(alternatives), 2)
        self.assertEqual(len(signatures), len(set(signatures)))
        for index, signature in enumerate(signatures):
            for other in signatures[index + 1:]:
                self.assertFalse(signature <= other or other <= signature)
        self.assertEqual({p["league"] for p in alternatives[0]}, {"eng.1", "tur.1", "esp.1"})
        self.assertTrue(all(p["id"] != 9 for coupon in alternatives for p in coupon))
        self.assertEqual(alternatives[0], select_banko(entries + [small]))

    def test_surprise_alternatives_are_unique_and_exclude_small_leagues(self):
        leagues = ("eng.1", "tur.1", "esp.1", "ger.1", "ita.1")
        entries = [entry(i, {"X": (0.35, 3.1)}, league=league) for i, league in enumerate(leagues, 1)]
        small = entry(9, {"X": (0.5, 5.0)}, league="small:country:league")
        small[0]["small_league"] = True
        alternatives = select_surprise_alternatives(entries + [small])
        signatures = [frozenset(p["id"] for p in coupon) for coupon in alternatives]
        self.assertEqual(len(alternatives), 3)
        self.assertEqual(len(signatures), len(set(signatures)))
        self.assertEqual({p["league"] for p in alternatives[0]}, {"eng.1", "tur.1", "esp.1"})
        self.assertTrue(all(p["id"] != 9 for coupon in alternatives for p in coupon))
        self.assertEqual(alternatives[0], select_surprise(entries + [small]))


class SmallLeagueCouponTest(unittest.TestCase):
    def test_small_leagues_are_excluded_from_existing_coupons(self):
        entries = [entry(1, {"1": (0.90, 1.3)}), entry(2, {"1": (0.90, 1.3)}),
                   entry(3, {"X": (0.3, 3.5)}), entry(4, {"X": (0.3, 3.5)}), entry(5, {"X": (0.3, 3.5)})]
        for p, _ in entries:
            p["small_league"] = True
        self.assertEqual(select_banko(entries), [])
        self.assertEqual(select_surprise(entries), [])

    def test_standard_selectors_exclude_small_flag(self):
        entries = [entry(i, {"1": (0.9, 1.3), "X": (0.3, 3.0)}) for i in range(1, 6)]
        for p, _ in entries:
            p["small_league"] = True
        self.assertEqual(select_banko(entries), [])
        self.assertEqual(select_surprise(entries), [])
        self.assertEqual(len(select_small_league(entries)), 4)

    def test_small_recommendation_uses_existing_probability_and_market_rules(self):
        p, choices = entry(1, {"1": (0.64, 1.55), "1X": (0.88, 1.12), "Ü2.5": (0.91, 1.1)},
                           {"1": 1.6}, league="small:iceland:premier-league")
        p["small_league"] = True
        self.assertEqual(small_league_recommendation(p, choices)["market"], "1X")

        p, choices = entry(2, {"1": (0.49, 1.9), "Ü2.5": (0.91, 1.1)},
                           league="small:iceland:premier-league")
        p["small_league"] = True
        self.assertIsNone(small_league_recommendation(p, choices))

    def test_standard_day_entries_filter_small_flag(self):
        now = datetime.now(timezone.utc) + timedelta(hours=3)
        kickoff = now.strftime("%Y-%m-%dT%H:%MZ")
        regular = {**pred(10, {"1": (0.8, 1.3)}, kickoff=kickoff), "iddaa_odds": {}}
        small = {**pred(11, {"1": (0.9, 1.2)}, kickoff=kickoff), "small_league": True, "iddaa_odds": {}}
        fake = type("M", (), {"upcoming_predictions": lambda self, d: [regular, small]})()
        with patch.object(cp, "LEAGUES", {"eng.1": {"name": "x"}}), \
             patch.object(cp.engine, "get_model", lambda l: fake), \
             patch.object(cp, "blend_predictions", lambda conn, xs: xs):
            entries = cp._day_entries(now.astimezone(cp.TZ).date())
        self.assertEqual([p["id"] for p, _ in entries], [10])

    def test_small_coupon_has_two_to_four_low_confidence_selections(self):
        entries = []
        for i in range(1, 6):
            p = pred(i, {"1": (0.66, 1.5), "1X": (0.82, 1.2)}, league=f"small:country:league")
            p["small_league"] = True
            p["league_name"] = "Premier League"
            entries.append((p, _choices(p, {"1": 1.55})))
        with patch.object(cp, "LEAGUES", {}):
            picks = select_small_league(entries)
        self.assertEqual(len(picks), 4)
        self.assertTrue(all(p["small_league"] and p["confidence"] == "Düşük" for p in picks))



class BuildCouponsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patcher = patch.object(db, "DB_PATH", Path(self.tmp.name) / "t.db")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        db.init_db()

    def test_empty_day_and_no_iddaa_data(self):
        with patch.object(cp, "LEAGUES", {}):
            r = cp.build_coupons(date(2026, 1, 1))
        self.assertEqual((r["banko"]["picks"], r["surprise"]["picks"], r["matches"]), ([], [], 0))
        self.assertEqual((r["banko_alternatives"], r["surprise_alternatives"]), ([], []))

    def test_build_scans_main_leagues_together_and_keeps_legacy_coupon_fields(self):
        target = (datetime.now(cp.TZ) + timedelta(days=2)).date()
        kickoff = datetime.combine(target, datetime.min.time(), cp.TZ).replace(hour=18).isoformat()
        leagues = {f"league.{i}": {"name": f"Liga {i}"} for i in range(1, 6)}
        predictions = {league: [{**pred(i, {"1": (0.82 - i * 0.01, 1.35), "X": (0.35, 3.1)},
                                                 kickoff=kickoff, league=league), "iddaa_odds": {}}]
                       for i, league in enumerate(leagues, 1)}
        fake_models = {league: type("M", (), {"upcoming_predictions": lambda self, days, p=items: p})()
                       for league, items in predictions.items()}
        with patch.object(cp, "LEAGUES", leagues), \
             patch.object(cp.engine, "get_model", lambda league: fake_models[league]), \
             patch.object(cp, "blend_predictions", lambda conn, items: items):
            result = cp.build_coupons(target)

        self.assertEqual(result["matches"], 5)
        self.assertGreaterEqual(len(result["banko_alternatives"]), 2)
        self.assertGreaterEqual(len(result["surprise_alternatives"]), 2)
        self.assertEqual(result["banko"], result["banko_alternatives"][0])
        self.assertEqual(result["surprise"], result["surprise_alternatives"][0])
        self.assertTrue(all(c["type"] == "banko" for c in result["banko_alternatives"]))
        self.assertTrue(all(c["type"] == "surprise" for c in result["surprise_alternatives"]))
        self.assertEqual(result["small_leagues"]["picks"], [])

    def test_day_uses_istanbul_time_and_skips_started_matches(self):
        now = datetime.now(timezone.utc)
        late = (now + timedelta(days=2)).replace(hour=21, minute=30, second=0, microsecond=0)  # 00:30 TR ertesi gün
        started = now - timedelta(minutes=30)
        fmt = lambda t: t.strftime("%Y-%m-%dT%H:%MZ")
        fake = type("M", (), {"upcoming_predictions": lambda self, d: [
            pred(1, {"1": (0.8, 1.3)}, kickoff=fmt(late)), pred(2, {"1": (0.8, 1.3)}, kickoff=fmt(started))]})()
        with patch.object(cp, "LEAGUES", {"eng.1": {"name": "x"}}), patch.object(cp.engine, "get_model", lambda l: fake):
            same_utc_day = cp.build_coupons(late.date())
            istanbul_day = cp.build_coupons((late + timedelta(hours=3)).date())
            today = cp.build_coupons(started.astimezone(cp.TZ).date())
        self.assertEqual(same_utc_day["matches"], 0)
        self.assertEqual(istanbul_day["matches"], 1)
        self.assertEqual(today["matches"], 0)

    def test_endpoint_day_validation(self):
        with self.assertRaises(HTTPException) as ctx:
            coupons_endpoint(day="17-10-2026")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_small_picks_endpoint_reads_existing_event_and_odds_fields(self):
        kickoff = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        small_id = 'small-1" data-markup="<img src=x onerror=alert(1)>'
        with db.session() as conn:
            conn.execute(
                """INSERT INTO iddaa_events
                   (id, league, competition_id, kickoff, home, away, league_name, country, is_small, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (small_id, "small:iceland:premier-league", 123, kickoff, "North FC", "South FC",
                 "İzlanda · Premier League", "İzlanda", 1, kickoff))
            for market, odd in (("1", 1.3), ("X", 6.0), ("2", 9.0)):
                conn.execute("INSERT INTO iddaa_odds(event_id, market, odd) VALUES (?, ?, ?)",
                             (small_id, market, odd))

        result = picks_endpoint(category="small", days=7, min_conf=0.99)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], small_id)
        self.assertEqual(result[0]["country"], "İzlanda")
        self.assertEqual(result[0]["league_name"], "İzlanda · Premier League")
        self.assertEqual(result[0]["event_id"], small_id)
        self.assertEqual(result[0]["iddaa_event_id"], small_id)
        self.assertEqual(result[0]["competition_id"], 123)
        self.assertEqual(result[0]["pick"]["market"], "1")
        self.assertEqual(result[0]["pick"]["odds"], 1.3)
        self.assertEqual(result[0]["pick"]["odds_source"], "iddaa")
        self.assertEqual(result[0]["pick"]["probability_source"], "iddaa_market")
        self.assertIsNone(result[0]["pick"]["suggested"])
        self.assertEqual(result[0]["recommendation_source"], "iddaa_market")
        self.assertEqual(result[0]["recommendation_label"], "İddaa piyasa favorisi")
        self.assertIsNone(result[0]["confidence"])
        self.assertEqual(result[0]["confidence_label"], "Düşük · model güveni yok")
        self.assertFalse(result[0]["confidence_filter_applied"])
        self.assertTrue(result[0]["small_league"])


if __name__ == "__main__":
    unittest.main()
