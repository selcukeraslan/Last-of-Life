"""Değerli oranlar: modelin olasılığı ile iddaa.com oranını karşılaştırır.

EV = p x oran - 1. Yalnız EV > 0 olan seçimler listelenir; iddaa oranı olmayan pazarlar
(veya maçlar) hiç değerlendirilmez. Sonuçlar EV'ye göre azalan sıradadır.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from .config import LEAGUES
from .db import get_meta, session
from .model import engine
from .model import extra_markets
from .scrapers import iddaa

router = APIRouter()

DEFAULT_DAYS = 7


def market_group(selection: str) -> str:
    """Seçimin ait olduğu iddaa pazarının Türkçe adı ("Ü2.5" -> "Alt/Üst 2.5")."""
    if selection.startswith("İY/MS "):
        return "İY/MS"
    if selection.startswith("İY "):
        return "İlk Yarı"
    if selection.startswith("Handikap "):
        return "Handikaplı Maç Sonucu"
    if selection.startswith("Korner "):
        return "Toplam Korner Alt/Üst"
    if selection.startswith("Kart "):
        return "Toplam Kart Alt/Üst"
    if selection in ("1", "X", "2"):
        return "Maç Sonucu"
    if selection in ("1X", "12", "X2"):
        return "Çifte Şans"
    if selection.startswith("KG"):
        return "Karşılıklı Gol"
    if selection[:1] in ("Ü", "A") and selection[1:].replace(".", "").isdigit():
        return f"Alt/Üst {selection[1:]}"
    return selection


def collect(predictions: list[dict], odds_by_match: dict[str, dict],
            min_prob: float = 0.0, min_ev: float = 0.0) -> dict:
    """Tahminler + iddaa oranlarından değerli seçimleri üretir (G/Ç yok, test edilebilir)."""
    with_odds = positive = 0
    items = []
    for pred in predictions:
        if pred.get("small_league") or str(pred.get("league", "")).startswith("small:"):
            continue
        source = odds_by_match.get(str(pred["id"]))
        odds = (source or {}).get("odds") or {}
        model_markets = dict(pred.get("markets") or {})
        if "lambda_home" in pred and "lambda_away" in pred:
            model_markets.update(extra_markets.for_match(pred["lambda_home"], pred["lambda_away"], odds))
        found = False
        for selection, odd in odds.items():
            model = model_markets.get(selection)
            if not model or model.get("p") is None or not odd or odd <= 1:
                continue
            found = True
            ev = model["p"] * odd - 1
            if ev <= 0:
                continue
            positive += 1
            if model["p"] < min_prob or ev < min_ev:
                continue
            items.append({
                "id": pred["id"], "league": pred["league"], "league_name": LEAGUES[pred["league"]]["name"],
                "kickoff": pred["kickoff"], "home": pred["home"], "away": pred["away"],
                "market": market_group(selection), "selection": selection,
                "model_probability": model["p"], "iddaa_odds": round(odd, 2),
                "implied_probability": round(1 / odd, 4), "ev": round(ev, 4),
                "iddaa_updated_at": source["updated_at"],
            })
        with_odds += found
    items.sort(key=lambda x: (-x["ev"], x["kickoff"]))
    return {"matches": len(predictions), "matches_with_odds": with_odds,
            "positive_ev_total": positive, "items": items}


def explain_empty(result: dict, days: int, min_prob: float, min_ev: float) -> str | None:
    """Liste boşsa nedenini anlatan mesaj; doluysa None."""
    if result["items"]:
        return None
    if not result["matches"]:
        return f"Önümüzdeki {days} günde model tahmini olan maç yok. Verileri güncellemeyi deneyin."
    if not result["matches_with_odds"]:
        return (f"{result['matches']} yaklaşan maç için iddaa.com oranı bulunamadı; oranlar henüz açılmamış "
                "veya maçlarla eşleşmemiş olabilir. Verileri güncellemeyi deneyin.")
    if result["positive_ev_total"]:
        return (f"{result['positive_ev_total']} değerli seçim var ancak seçili filtrelerin "
                f"(min. olasılık %{min_prob * 100:.0f}, min. EV %{min_ev * 100:.0f}) dışında kaldı; filtreleri gevşetin.")
    return (f"iddaa oranı bulunan {result['matches_with_odds']} maçta modelin olasılığı iddaa oranını "
            "geçen (EV > 0) seçim yok.")


def build_value_bets(days: int = DEFAULT_DAYS, min_prob: float = 0.0, min_ev: float = 0.0) -> dict:
    now = datetime.now(timezone.utc)
    predictions = []
    for league in LEAGUES:
        for p in engine.get_model(league).upcoming_predictions(days):
            if datetime.fromisoformat(p["kickoff"].replace("Z", "+00:00")) > now:  # başlamış maça oran yok
                predictions.append(p)
    small_count = 0
    with session() as conn:
        small_count = conn.execute("SELECT COUNT(DISTINCT id) n FROM iddaa_events WHERE is_small=1").fetchone()["n"]
        odds = iddaa.odds_for_matches(conn, [p["id"] for p in predictions])
        last_update = get_meta(conn, "iddaa_last_update")
    result = collect(predictions, odds, min_prob, min_ev)
    return {"days": days, "min_probability": min_prob, "min_ev": min_ev, "iddaa_last_update": last_update,
            "small_leagues_excluded": small_count,
            **result, "message": explain_empty(result, days, min_prob, min_ev)}


@router.get("/api/value-bets")
def value_bets(days: int = Query(DEFAULT_DAYS, ge=1, le=30),
               min_prob: float = Query(0.0, ge=0, le=1, description="Modelin min. olasılığı (0-1)"),
               min_ev: float = Query(0.0, ge=0, le=10, description="Min. EV (0.05 = %5)")):
    return build_value_bets(days, min_prob, min_ev)
