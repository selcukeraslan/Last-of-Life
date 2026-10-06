"""Kupon geçmişi endpoint'i (app/model/coupon_history.py)."""
from fastapi import APIRouter, Query

from .db import session
from .model import coupon_history

router = APIRouter()


@router.get("/api/coupon-history")
def get_coupon_history(days: int = Query(60, ge=1, le=365, description="Listelenecek en yeni gün sayısı")):
    """Dondurulmuş Banko/Sürpriz kuponları, sonuç durumları ve 'her gün 100 TL' kâr/zarar özeti."""
    with session() as conn:
        return coupon_history.history(conn, days)
