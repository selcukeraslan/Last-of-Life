"""FastAPI uygulaması. Çalıştırma: ./run.sh  (veya .venv/bin/uvicorn app.main:app)"""
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import updater
from .config import LEAGUES, MODEL, STATIC_DIR
from .db import get_meta, init_db, session
from .model import engine
from .model.ratings import parse_ts

AUTO_UPDATE_HOURS = 6


@asynccontextmanager
async def lifespan(_app):
    init_db()
    with session() as conn:
        last = get_meta(conn, "last_update")
    if not last or datetime.now(timezone.utc) - parse_ts(last) > timedelta(hours=AUTO_UPDATE_HOURS):
        updater.run_in_background()  # veri eskiyse açılışta arka planda güncelle
    yield


app = FastAPI(title="İddia Oran Öneri", lifespan=lifespan)


def _check_league(league: str):
    if league not in LEAGUES:
        raise HTTPException(404, "Bilinmeyen lig")


@app.get("/api/leagues")
def leagues():
    with session() as conn:
        rows = {r["league"]: dict(r) for r in conn.execute(
            "SELECT league, COUNT(*) total, SUM(completed) played FROM matches GROUP BY league")}
        last = get_meta(conn, "last_update")
    return {"last_update": last, "model": MODEL,
            "leagues": [{"id": k, **v, "total": rows.get(k, {}).get("total", 0),
                         "played": rows.get(k, {}).get("played", 0)} for k, v in LEAGUES.items()]}


@app.get("/api/upcoming")
def upcoming(league: str, days: int = Query(14, ge=1, le=30)):
    _check_league(league)
    return engine.get_model(league).upcoming_predictions(days)


@app.get("/api/match/{match_id}")
def match(match_id: str):
    for lg in LEAGUES:
        m = next((x for x in engine.get_model(lg).upcoming if x["id"] == match_id), None)
        if m:
            model = engine.get_model(lg)
            p = model.predict(m["home"], m["away"], m["ts"])
            return {"id": m["id"], "league": lg, "league_name": LEAGUES[lg]["name"], "kickoff": m["kickoff"],
                    "home": m["home"], "away": m["away"],
                    "home_logo": engine._logo(m["home_id"]), "away_logo": engine._logo(m["away_id"]), **p}
    raise HTTPException(404, "Maç bulunamadı")


@app.get("/api/standings")
def standings(league: str):
    _check_league(league)
    m = engine.get_model(league)
    elo = m.elo
    return [{**r, "elo": round(elo.get(r["team"]))} for r in m.table]


@app.get("/api/picks")
def picks(days: int = Query(7, ge=1, le=21), min_conf: float = 0.0):
    """Tüm liglerden en güvenilir önerileri döndürür."""
    out = []
    for lg in LEAGUES:
        for p in engine.get_model(lg).upcoming_predictions(days):
            if p.get("pick") and p["confidence"] >= min_conf:
                out.append({"id": p["id"], "league": lg, "league_name": LEAGUES[lg]["name"],
                            "kickoff": p["kickoff"], "home": p["home"], "away": p["away"],
                            "pick": p["pick"], "confidence": p["confidence"],
                            "confidence_label": p["confidence_label"],
                            "score": p["pick"]["p"] * (0.5 + p["confidence"])})
    out.sort(key=lambda x: -x["score"])
    return out


@app.post("/api/update")
def start_update(news: bool = True):
    started = updater.run_in_background(with_news=news)
    return {"started": started, **updater.state()}


@app.get("/api/update/status")
def update_status():
    return updater.state()


_bt_lock = threading.Lock()
_bt_state = {"running": False}


@app.get("/api/backtest")
def get_backtest():
    return {"running": _bt_state["running"], "data": engine.cached_backtest()}


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
