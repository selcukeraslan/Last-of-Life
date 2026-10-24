"""Günlük, ligler arası kupon seçimi (Banko + Sürpriz).

Olasılıklar iddaa.com oranlarıyla harmanlıdır (model/blend.py; oran yoksa model aynen).
Oran önceliği: eşleşen iddaa.com oranı varsa o kullanılır, yoksa Claude oranı (modelin
önerilen oranı). Her seçimde hangi oranın kullanıldığı `odds_source` alanında döner.
Gün sınırı Türkiye saatidir (arayüzdeki saatler de yerel gösterilir).
"""
import math
from datetime import date, datetime, timezone, timedelta
from itertools import combinations
from zoneinfo import ZoneInfo

from ..config import LEAGUES
from ..db import session
from . import engine
from .blend import blend_predictions
from .settlement import SUPPORTED_MARKETS

TZ = ZoneInfo("Europe/Istanbul")
LOOKAHEAD_DAYS = 60

BANKO_MIN_P = 0.75
BANKO_MIN_ODDS = 1.15
BANKO_MIN_TOTAL_P = 0.50
BANKO_PICKS = (2, 3)
BANKO_POOL = 14
BANKO_ALTERNATIVES = 3

SURPRISE_MIN_P = 0.20
SURPRISE_MAX_P = 0.62
SURPRISE_MIN_ODDS = 1.55
SURPRISE_MIN_TOTAL_ODDS = 15.0
SURPRISE_PICKS = (3, 5)
SURPRISE_POOL = 14  # kombinasyon aramasına giren en değerli aday sayısı
SURPRISE_ALTERNATIVES = 3
SURPRISE_MARKETS = {"X", "2", "Ü2.5", "Ü3.5", "KG Var", "A2.5"}


def _choices(prediction: dict, iddaa_odds: dict) -> list[dict]:
    """Bir maçın seçilebilir pazarları; oran = iddaa varsa iddaa, yoksa Claude oranı."""
    out = []
    available = {**prediction.get("markets", {}), **prediction.get("extra_markets", {})}
    for market, item in available.items():
        if market not in SUPPORTED_MARKETS:
            continue  # ilk yarı/handikap için ortak sonuç verisi henüz tutulmuyor
        if item.get("p") is None:  # korner/kart için geçmiş veri yok; oranı kupona model gibi sokma
            continue
        claude = item.get("suggested")
        if not claude or claude < 1.01:
            continue
        theirs = iddaa_odds.get(market)
        odds, source = (round(theirs, 2), "iddaa") if theirs and theirs >= 1.01 else (claude, "claude")
        out.append({"market": market, "p": item["p"], "odds": odds, "odds_source": source,
                    "iddaa_odds": theirs if source == "iddaa" else None, "claude_odds": claude,
                    "fair": item.get("fair")})
    return out


def _match_view(prediction: dict, choice: dict) -> dict:
    return {"id": prediction["id"], "league": prediction["league"],
            "league_name": prediction.get("league_name") or LEAGUES.get(prediction["league"], {}).get("name", prediction["league"]),
            "kickoff": prediction["kickoff"],
            "home": prediction["home"], "away": prediction["away"], **choice,
            "model_probability": choice["p"]}


def small_league_recommendation(prediction: dict, choices: list[dict] | None = None) -> dict | None:
    """Küçük ligdeki maç için mevcut düşük güven seçim kuralına uyan en olası pazarı bul."""
    choices = choices if choices is not None else _choices(prediction, prediction.get("iddaa_odds", {}))
    valid = [c for c in choices if c["market"] in {"1", "1X", "X2", "2"} and c["p"] >= 0.50]
    return max(valid, key=lambda c: (c["p"], -c["odds"])) if valid else None


def _coupon(kind: str, picks: list[dict], note: str) -> dict:
    sources = {p["odds_source"] for p in picks}
    source = sources.pop() if len(sources) == 1 else ("karışık" if sources else None)
    return {"type": kind, "picks": picks, "stake_note": note, "odds_source": source,
            "iddaa_picks": sum(p["odds_source"] == "iddaa" for p in picks),
            "total_odds": round(math.prod(p["odds"] for p in picks), 2) if picks else 0,
            "total_probability": round(math.prod(p["p"] for p in picks), 4) if picks else 0}


def select_banko(entries: list[tuple[dict, list[dict]]]) -> list[dict]:
    """Maç başı en olası uygun pazar; en olası 2-3 maç, toplam tutma >= %50. Her maçtan tek seçim."""
    best = []
    for prediction, choices in entries:
        if prediction.get("small_league") or str(prediction.get("league", "")).startswith("small:"):
            continue
        ok = [c for c in choices if c["p"] >= BANKO_MIN_P and c["odds"] >= BANKO_MIN_ODDS]
        if ok:
            best.append((prediction, max(ok, key=lambda c: (c["p"], c["odds"]))))
    best.sort(key=lambda x: (-x[1]["p"], -x[1]["odds"]))
    picks = [_match_view(p, c) for p, c in best[:BANKO_PICKS[1]]]
    while len(picks) > BANKO_PICKS[0] and math.prod(x["p"] for x in picks) < BANKO_MIN_TOTAL_P:
        picks.pop()
    if len(picks) < BANKO_PICKS[0] or math.prod(x["p"] for x in picks) < BANKO_MIN_TOTAL_P:
        return []
    return picks


def select_banko_alternatives(entries: list[tuple[dict, list[dict]]], limit: int = BANKO_ALTERNATIVES) -> list[list[dict]]:
    """Uygun ana lig seçimlerinden, en iyi Banko kuponunu ilk sırada tutarak farklı alternatifler üret."""
    primary = select_banko(entries)
    if not primary or limit <= 0:
        return []

    pool, seen_matches = [], set()
    for prediction, choices in entries:
        if prediction.get("small_league") or str(prediction.get("league", "")).startswith("small:"):
            continue
        match_id = str(prediction.get("id", ""))
        if not match_id or match_id in seen_matches:
            continue
        ok = [c for c in choices if c["p"] >= BANKO_MIN_P and c["odds"] >= BANKO_MIN_ODDS]
        if ok:
            pool.append((prediction, max(ok, key=lambda c: (c["p"], c["odds"]))))
            seen_matches.add(match_id)
    pool.sort(key=lambda x: (-x[1]["p"], -x[1]["odds"]))
    pool = pool[:BANKO_POOL]

    alternatives = [primary]
    signatures = {frozenset((str(p["id"]), p["market"]) for p in primary)}
    candidates = []
    for size in range(BANKO_PICKS[0], BANKO_PICKS[1] + 1):
        for combo in combinations(pool, size):
            if math.prod(c["p"] for _, c in combo) < BANKO_MIN_TOTAL_P:
                continue
            picks = [_match_view(p, c) for p, c in combo]
            signature = frozenset((str(p["id"]), p["market"]) for p in picks)
            if signature in signatures:
                continue
            key = (round(math.prod(p["p"] for p in picks), 4), len(picks), math.prod(p["odds"] for p in picks))
            candidates.append((key, picks, signature))
    candidates.sort(key=lambda item: item[0], reverse=True)
    for _, picks, signature in candidates:
        if any(signature <= chosen or chosen <= signature for chosen in signatures):
            continue
        alternatives.append(picks)
        signatures.add(signature)
        if len(alternatives) >= limit:
            break
    return alternatives


def select_surprise(entries: list[tuple[dict, list[dict]]]) -> list[dict]:
    """3-5 farklı maç, toplam oran >= 15. Maç başı seçim EV'ye (p x oran - 1) göre; kuponda oran
    iddaa oranıysa gerçek, değilse Claude oranına göre EV'dir. En değerli adaylar arasından toplam
    oran >= 15 şartını sağlayan, tutma olasılığı en yüksek kombinasyon seçilir (eşitlikte birleşik EV)."""
    alternatives = select_surprise_alternatives(entries, limit=1)
    return alternatives[0] if alternatives else []


def select_surprise_alternatives(entries: list[tuple[dict, list[dict]]], limit: int = SURPRISE_ALTERNATIVES) -> list[list[dict]]:
    """Tüm ana lig maçlarını ortak havuzda değerlendirip en iyi Sürpriz alternatiflerini üret."""
    if limit <= 0:
        return []
    pool, seen_matches = [], set()
    for prediction, choices in entries:
        if prediction.get("small_league") or str(prediction.get("league", "")).startswith("small:"):
            continue
        match_id = str(prediction.get("id", ""))
        if not match_id or match_id in seen_matches:
            continue
        ok = [dict(c, value=round(c["p"] * c["odds"] - 1, 4)) for c in choices
              if c["market"] in SURPRISE_MARKETS and SURPRISE_MIN_P <= c["p"] <= SURPRISE_MAX_P
              and c["odds"] >= SURPRISE_MIN_ODDS]
        if ok:
            pool.append((prediction, max(ok, key=lambda c: (c["value"], c["p"] * c["odds"] ** 0.35))))
            seen_matches.add(match_id)
    pool.sort(key=lambda x: (x[1]["value"], x[1]["p"] * x[1]["odds"] ** 0.35), reverse=True)
    pool = pool[:SURPRISE_POOL]

    candidates = []
    for size in range(SURPRISE_PICKS[0], SURPRISE_PICKS[1] + 1):
        for combo in combinations(pool, size):
            if math.prod(c["odds"] for _, c in combo) < SURPRISE_MIN_TOTAL_ODDS:
                continue
            key = (round(math.prod(c["p"] for _, c in combo), 4),
                   math.prod(c["p"] * c["odds"] for _, c in combo))
            picks = [_match_view(p, c) for p, c in sorted(combo, key=lambda x: x[0]["kickoff"])]
            signature = frozenset((str(p["id"]), p["market"]) for p in picks)
            candidates.append((key, picks, signature))
    candidates.sort(key=lambda item: item[0], reverse=True)
    alternatives, signatures = [], set()
    for _, picks, signature in candidates:
        if signature in signatures:
            continue
        alternatives.append(picks)
        signatures.add(signature)
        if len(alternatives) >= limit:
            break
    return alternatives


def _day_entries(target: date) -> list[tuple[dict, list[dict]]]:
    now = datetime.now(timezone.utc)
    predictions = []
    for league in LEAGUES:
        for p in engine.get_model(league).upcoming_predictions(LOOKAHEAD_DAYS):
            kickoff = datetime.fromisoformat(p["kickoff"].replace("Z", "+00:00"))
            if kickoff > now and kickoff.astimezone(TZ).date() == target and not p.get("small_league"):
                predictions.append(p)
    with session() as conn:
        predictions = blend_predictions(conn, predictions)  # olasılıklar iddaa ile harmanlı
    return [(p, _choices(p, p["iddaa_odds"])) for p in predictions]


def select_small_league(entries: list[tuple[dict, list[dict]]]) -> list[dict]:
    """Küçük liglerde 2-4 en olası ayrı maç; oranla tahmini harmanla ve güveni düşük tut."""
    best = []
    for prediction, choices in entries:
        if not prediction.get("small_league"):
            continue
        choice = small_league_recommendation(prediction, choices)
        if choice:
            best.append((prediction, choice))
    best.sort(key=lambda item: (-item[1]["p"], item[0]["kickoff"]))
    picks = []
    for prediction, choice in best[:4]:
        pick = _match_view(prediction, choice)
        pick.update({"confidence": "Düşük", "small_league": True})
        picks.append(pick)
    return picks if len(picks) >= 2 else []


def build_coupons(target: date) -> dict:
    entries = _day_entries(target)
    with session() as conn:
        rows = conn.execute(
            """SELECT e.id, e.league, e.league_name, e.country, e.kickoff, e.home, e.away,
                      o.market, o.odd
               FROM iddaa_events e LEFT JOIN iddaa_odds o ON o.event_id=e.id
               WHERE e.is_small=1 AND e.kickoff>=? AND e.kickoff<=? ORDER BY e.kickoff""",
            (datetime.combine(target, datetime.min.time(), TZ).astimezone(timezone.utc).isoformat(),
             datetime.combine(target + timedelta(days=1), datetime.min.time(), TZ)
             .astimezone(timezone.utc).isoformat())).fetchall()
    grouped = {}
    for r in rows:
        p = grouped.setdefault(r["id"], {"id": r["id"], "league": r["league"], "country": r["country"],
            "league_name": r["league_name"], "kickoff": r["kickoff"],
            "home": r["home"], "away": r["away"], "iddaa_odds": {}, "small_league": True})
        if r["market"] and r["odd"]:
            p["iddaa_odds"][r["market"]] = r["odd"]
    small_entries = []
    for event in grouped.values():
        p = _small_prediction_for_coupon(event)
        small_entries.append((p, _choices(p, p["iddaa_odds"])))
    small_picks = select_small_league(small_entries)
    small_coupon = _coupon("small", small_picks,
        "Küçük liglerde veri ve kadro bilgisi sınırlıdır; güven düşüktür. Küçük miktar kullanın, garanti değildir.")
    for pick in small_coupon["picks"]:
        pick["league_name"] = grouped[pick["id"]]["league_name"]
        pick["country"] = grouped[pick["id"]]["country"]
        pick["country"] = grouped[pick["id"]]["country"]
    banko_note = "Sadece kaybetmeyi göze alabileceğiniz tutarla oynayın."
    surprise_note = "Sürpriz kupon: küçük miktar kullanın; garanti değildir."
    banko_alternatives = [_coupon("banko", picks, banko_note)
                          for picks in select_banko_alternatives(entries)]
    surprise_alternatives = [_coupon("surprise", picks, surprise_note)
                             for picks in select_surprise_alternatives(entries)]
    return {
        "date": target.isoformat(),
        "matches": len(entries),
        # Kupon geçmişi ve Telegram mevcut tek-kupon alanlarını kullanmayı sürdürür.
        "banko": banko_alternatives[0] if banko_alternatives else _coupon("banko", [], banko_note),
        "surprise": surprise_alternatives[0] if surprise_alternatives else _coupon("surprise", [], surprise_note),
        "banko_alternatives": banko_alternatives,
        "surprise_alternatives": surprise_alternatives,
        "small_leagues": small_coupon,
        "rules": {"banko_min_probability": BANKO_MIN_P, "banko_min_total_probability": BANKO_MIN_TOTAL_P,
                  "banko_min_odds": BANKO_MIN_ODDS,
                  "surprise_probability_range": [SURPRISE_MIN_P, SURPRISE_MAX_P],
                  "surprise_min_total_odds": SURPRISE_MIN_TOTAL_ODDS},
    }


def _small_prediction_for_coupon(event):
    from .small_leagues import predict_event
    return predict_event(event)
