"""FastAPI uygulaması. Çalıştırma: ./run.sh  (veya .venv/bin/uvicorn app.main:app)"""
import json
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone, date

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import odds_history, odds_log, pwa, updater
from . import live
from .api_odds_history import router as odds_history_router
from .config import LEAGUES, MODEL, STATIC_DIR
from .db import get_meta, init_db, is_postgres, session
from .coupon_history_api import router as coupon_history_router
from .model import coupon_history, engine
from .model.blend import blend_predictions
from .model.coupons import TZ, build_coupons, small_league_recommendation
from .model.ratings import parse_ts
from .value_bets import router as value_bets_router

AUTO_UPDATE_HOURS = 6


@asynccontextmanager
async def lifespan(_app):
    init_db()
    if not is_postgres():  # yerel geliştirme: veri eskiyse açılışta arka planda güncelle
        with session() as conn:
            last = get_meta(conn, "last_updated_at") or get_meta(conn, "last_update")
        if not last or datetime.now(timezone.utc) - parse_ts(last) > timedelta(hours=AUTO_UPDATE_HOURS):
            updater.run_in_background()
    yield  # Postgres (serverless): arka plan işi yok; güncelleme istek içinde veya cron'da


app = FastAPI(title="İddia Oran Öneri", lifespan=lifespan)
app.include_router(pwa.router)  # /manifest.webmanifest, /sw.js
app.include_router(odds_history_router)
app.include_router(coupon_history_router)
app.include_router(value_bets_router)


def _check_league(league: str):
    if league not in LEAGUES:
        raise HTTPException(404, "Bilinmeyen lig")


def _attach_iddaa_odds(items: list[dict]) -> list[dict]:
    """Tahmin yanıtlarına aynı ESPN maçıyla eşleşen güncel iddaa oranlarını ekler ve (`markets` içeren
    tahminlerde) olasılıkları marjı temizlenmiş iddaa olasılıklarıyla harmanlar (model/blend.py)."""
    if not items:
        return items
    with session() as conn:
        blended = blend_predictions(conn, items)
        movements = odds_history.movements_for_matches(conn, [item["id"] for item in items])
    for item in blended:
        item["iddaa_movement"] = movements.get(str(item["id"]), {})
    return blended


@app.get("/api/leagues")
def leagues():
    with session() as conn:
        rows = {r["league"]: dict(r) for r in conn.execute(
            "SELECT league, COUNT(*) total, SUM(completed) played FROM matches GROUP BY league")}
        last = get_meta(conn, "last_updated_at") or get_meta(conn, "last_update")
        iddaa_last = get_meta(conn, "iddaa_last_update")
        iddaa_error = get_meta(conn, "iddaa_last_error")
        iddaa_stats = json.loads(get_meta(conn, "iddaa_stats", "null"))
        small = [dict(r) for r in conn.execute(
            "SELECT league, MAX(league_name) league_name, MAX(country) country, COUNT(*) total "
            "FROM iddaa_events WHERE is_small=1 GROUP BY league ORDER BY country, league_name")]
    return {"last_update": last, "model": MODEL,
            "iddaa": {"last_update": iddaa_last, "error": iddaa_error, "stats": iddaa_stats},
            "leagues": [{"id": k, **v, "total": rows.get(k, {}).get("total", 0),
                         "played": rows.get(k, {}).get("played", 0), "category": "main"} for k, v in LEAGUES.items()],
            "small_leagues": [{"id": r["league"], "name": r["league_name"], "country": r["country"],
                               "total": r["total"], "played": 0, "category": "small"} for r in small]}


@app.get("/api/live")
def live_scores():
    return {"matches": live.get_live_matches(), "updated_at": datetime.now(timezone.utc).isoformat()}


@app.get("/api/upcoming")
def upcoming(league: str, days: int = Query(14, ge=1, le=30)):
    if league.startswith("small:"):
        now = datetime.now(timezone.utc)
        with session() as conn:
            rows = conn.execute(
                """SELECT e.id, e.league, e.league_name, e.country, e.kickoff, e.home, e.away,
                          o.market, o.odd
                   FROM iddaa_events e LEFT JOIN iddaa_odds o ON o.event_id=e.id
                   WHERE e.is_small=1 AND e.league=? AND e.kickoff>=? AND e.kickoff<=?
                   ORDER BY e.kickoff""",
                (league, now.isoformat(), (now + timedelta(days=days)).isoformat())).fetchall()
        grouped = {}
        for r in rows:
            item = grouped.setdefault(r["id"], {"id": r["id"], "league": league,
                "league_name": r["league_name"], "country": r["country"], "kickoff": r["kickoff"],
                "home": r["home"], "away": r["away"], "iddaa_odds": {}, "small_league": True})
            if r["market"] and r["odd"]:
                item["iddaa_odds"][r["market"]] = r["odd"]
        return [_small_prediction(item) for item in grouped.values()]
    _check_league(league)
    items = _attach_iddaa_odds(engine.get_model(league).upcoming_predictions(days))
    for item in items:
        item["league_name"] = LEAGUES[league]["name"]
    return items


def _small_prediction(event: dict) -> dict:
    """Marjı temizlenmiş bülten olasılığı, küçük liglerde düşük güven etiketiyle sunulur."""
    from .model.small_leagues import predict_event
    return predict_event(event)


@app.get("/api/match/{match_id}")
def match(match_id: str):
    with session() as conn:
        small = conn.execute("SELECT * FROM iddaa_events WHERE id=? AND is_small=1", (match_id,)).fetchone()
        if small:
            odds = {r["market"]: r["odd"] for r in conn.execute(
                "SELECT market, odd FROM iddaa_odds WHERE event_id=?", (match_id,)).fetchall()}
            event = {"id": small["id"], "league": small["league"], "league_name": small["league_name"],
                "country": small["country"], "kickoff": small["kickoff"], "home": small["home"],
                "away": small["away"], "iddaa_odds": odds, "small_league": True}
            result = _small_prediction(event)
            result["league_name"] = f"{small['country']} · {small['league_name']}"
            result["factors"] = {"table": {"home": None, "away": None},
                "elo": {"home": 1500, "away": 1500, "lambda_home": result["lambda_home"], "lambda_away": result["lambda_away"]},
                "poisson": {"att_home": 1, "att_away": 1, "def_home": 1, "def_away": 1,
                            "home": result["lambda_home"], "away": result["lambda_away"]},
                "form": {"home": "", "away": ""}, "news": {"home": {"score": 0, "injuries": 0}, "away": {"score": 0, "injuries": 0}},
                "rest_days": {"home": None, "away": None}}
            result["scores"] = []
            return result
    for lg in LEAGUES:
        m = next((x for x in engine.get_model(lg).upcoming if x["id"] == match_id), None)
        if m:
            model = engine.get_model(lg)
            p = model.predict(m["home"], m["away"], m["ts"])
            result = {"id": m["id"], "league": lg, "league_name": LEAGUES[lg]["name"], "kickoff": m["kickoff"],
                      "home": m["home"], "away": m["away"],
                      "home_logo": engine._logo(m["home_id"]), "away_logo": engine._logo(m["away_id"]), **p}
            return _attach_iddaa_odds([result])[0]
    raise HTTPException(404, "Maç bulunamadı")


@app.get("/api/standings")
def standings(league: str):
    _check_league(league)
    m = engine.get_model(league)
    elo = m.elo
    return [{**r, "elo": round(elo.get(r["team"]))} for r in m.table]


def _small_league_name(country: str | None, league_name: str | None) -> str:
    name = league_name or ""
    if not country:
        return name
    prefix = f"{country} · "
    if name.startswith(prefix):
        return name
    return f"{prefix}{name}" if name else country


def _small_pick(prediction: dict) -> dict | None:
    choice = small_league_recommendation(prediction)
    if not choice:
        return None
    return {"market": choice["market"], "p": choice["p"], "suggested": choice["claude_odds"]}


def _small_league_picks(days: int, min_conf: float = 0.0) -> list[dict]:
    now = datetime.now(timezone.utc)
    with session() as conn:
        rows = conn.execute(
            """SELECT e.id, e.league, e.league_name, e.country, e.kickoff, e.home, e.away,
                      o.market, o.odd
               FROM iddaa_events e LEFT JOIN iddaa_odds o ON o.event_id=e.id
               WHERE e.is_small=1 AND e.kickoff>=? AND e.kickoff<=?
               ORDER BY e.kickoff""",
            (now.isoformat(), (now + timedelta(days=days)).isoformat())).fetchall()
    grouped = {}
    for row in rows:
        event = grouped.setdefault(row["id"], {
            "id": row["id"], "league": row["league"], "league_name": row["league_name"],
            "country": row["country"], "kickoff": row["kickoff"], "home": row["home"],
            "away": row["away"], "iddaa_odds": {}, "small_league": True,
        })
        if row["market"] and row["odd"]:
            event["iddaa_odds"][row["market"]] = row["odd"]

    picks = []
    for event in grouped.values():
        prediction = _small_prediction(event)
        if prediction["confidence"] < min_conf:
            continue
        pick = _small_pick(prediction)
        if not pick:
            continue
        picks.append({"id": prediction["id"], "league": prediction["league"],
                      "league_name": _small_league_name(prediction.get("country"), prediction.get("league_name")),
                      "country": prediction["country"],
                      "kickoff": prediction["kickoff"], "home": prediction["home"],
                      "away": prediction["away"], "pick": pick,
                      "confidence": prediction["confidence"],
                      "confidence_label": prediction["confidence_label"],
                      "small_league": True, "iddaa_odds": prediction["iddaa_odds"],
                      "score": pick["p"] * (0.5 + prediction["confidence"])})
    picks.sort(key=lambda item: (-item["score"], item["kickoff"]))
    return picks


@app.get("/api/picks")
def picks(days: int = Query(7, ge=1, le=21), min_conf: float = 0.0, category: str = "main"):
    """Ana lig veya küçük lig önerilerini döndürür."""
    if category == "small":
        return _small_league_picks(days, min_conf)
    if category != "main":
        raise HTTPException(400, "Bilinmeyen öneri kategorisi")
    predictions = [p for lg in LEAGUES for p in engine.get_model(lg).upcoming_predictions(days)
                   if not p.get("small_league")]
    out = []
    for p in _attach_iddaa_odds(predictions):  # öneri/güven harmanlı olasılıktan hesaplanır
        if p.get("pick") and p["confidence"] >= min_conf:
            out.append({"id": p["id"], "league": p["league"], "league_name": LEAGUES[p["league"]]["name"],
                        "kickoff": p["kickoff"], "home": p["home"], "away": p["away"],
                        "pick": p["pick"], "confidence": p["confidence"],
                        "confidence_label": p["confidence_label"], "blend": p["blend"],
                        "iddaa_odds": p["iddaa_odds"], "iddaa_event_id": p["iddaa_event_id"],
                        "iddaa_updated_at": p["iddaa_updated_at"], "iddaa_movement": p["iddaa_movement"],
                        "score": p["pick"]["p"] * (0.5 + p["confidence"])})
    out.sort(key=lambda x: -x["score"])
    return out


@app.get("/api/coupons")
def coupons(day: str | None = Query(None, description="YYYY-MM-DD (Türkiye saati); varsayılan bugün")):
    try:
        target = date.fromisoformat(day) if day else datetime.now(TZ).date()
    except ValueError as exc:
        raise HTTPException(400, "Gün YYYY-AA-GG biçiminde olmalı") from exc
    result = build_coupons(target)
    coupon_history.freeze_if_today(result)  # günün kuponu ilk üretildiği haliyle kaydedilir
    return result


@app.post("/api/update")
def start_update():
    """Hızlı artımlı güncelleme (iddaa oranları + ESPN son günler), istek içinde senkron çalışır.
    Son güncellemeden sonra 10 dk bekleme ve kilit vardır; ağır tam güncelleme cron'dadır."""
    return updater.run_quick_update()


@app.get("/api/update/status")
def update_status():
    return updater.status()


_bt_lock = threading.Lock()
_bt_state = {"running": False}


@app.get("/api/backtest")
def get_backtest():
    return {"running": _bt_state["running"], "data": engine.cached_backtest(),
            "odds_log": odds_log.current_summary()}


@app.post("/api/backtest")
def run_backtest():
    def job():
        try:
            engine.run_backtests()
        finally:
            _bt_state["running"] = False

    with _bt_lock:
        if not _bt_state["running"]:
            _bt_state["running"] = True
            threading.Thread(target=job, daemon=True).start()
    return {"running": True}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")
