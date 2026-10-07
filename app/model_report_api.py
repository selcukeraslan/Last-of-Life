"""Model Karnesi endpoint'i: cron'un önbelleğe yazdığı raporu döndürür (hızlı, hesap yapmaz)."""
from fastapi import APIRouter

from .model import report

router = APIRouter()


@router.get("/api/model-report")
def get_model_report():
    return report.cached() or {"computed_at": None, "overall": {"n": 0}, "leagues": [], "calibration": [],
                               "trend": [], "coupons": None}
