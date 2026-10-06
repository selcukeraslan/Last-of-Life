"""Oran geçmişi uç noktaları (main.py'de `app.include_router` ile eklenir)."""
from fastapi import APIRouter, HTTPException, Query

from . import odds_history
from .config import LEAGUES
from .db import session

router = APIRouter(prefix="/api/odds", tags=["odds-history"])


@router.get("/history/{match_id}")
def match_history(match_id: str):
    """Maçın pazar başına zaman damgalı iddaa oran serisi (açılıştan güncele)."""
    with session() as conn:
        data = odds_history.history_for_match(conn, match_id)
    if data is None:
        raise HTTPException(404, "Bu maç için iddaa oranı geçmişi yok")
    return data


@router.get("/drops")
def odds_drops(min_pct: float = Query(odds_history.DROP_THRESHOLD_PCT, ge=1, le=90),
               league: str | None = None, limit: int = Query(20, ge=1, le=100)):
    """Açılışa göre belirgin (varsayılan %10+) oran düşüşü olan yaklaşan maçlar."""
    if league and league not in LEAGUES:
        raise HTTPException(404, "Bilinmeyen lig")
    with session() as conn:
        return {"min_pct": min_pct, "matches": odds_history.drops(conn, min_pct, league, limit)}
