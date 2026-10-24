"""Model Karnesi endpoint'i: cron'un önbelleğe yazdığı raporu döndürür (hızlı, hesap yapmaz)."""
from fastapi import APIRouter

from .model import report, snapshots
from .db import session

router = APIRouter()


@router.get("/api/model-report")
def get_model_report():
    result = report.cached() or {"computed_at": None, "overall": {"n": 0}, "leagues": [], "calibration": [],
                               "trend": [], "coupons": None}
    with session() as conn:
        try:
            result["prospective"] = snapshots.report(conn)
        except Exception:
            conn.rollback()
            result["prospective"] = {"available": False}
    return result
