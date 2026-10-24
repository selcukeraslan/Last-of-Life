"""Tam maç skoruyla kesin sonuçlandırılabilen otomatik kupon pazarları."""
from datetime import datetime, timedelta

VOID_AFTER_DAYS = 7
VOID_STATUSES = ("postpon", "cancel", "abandon", "suspend")

SUPPORTED_MARKETS = frozenset({
    "1", "X", "2", "1X", "12", "X2", "KG Var", "KG Yok", "Ev 0.5Ü", "Dep 0.5Ü",
    *(f"{side}{line}" for side in ("A", "Ü") for line in ("1.5", "2.5", "3.5")),
})


def outcome(market: str, home_goals: int, away_goals: int) -> bool | None:
    if market not in SUPPORTED_MARKETS:
        return None
    h, a = home_goals, away_goals
    rules = {"1": h > a, "X": h == a, "2": h < a, "1X": h >= a, "12": h != a, "X2": h <= a,
             "KG Var": h > 0 and a > 0, "KG Yok": h == 0 or a == 0, "Ev 0.5Ü": h >= 1, "Dep 0.5Ü": a >= 1}
    if market in rules:
        return rules[market]
    line = float(market[1:])
    return h + a > line if market[0] == "Ü" else h + a < line


def selection_state(market, kickoff, now, *, completed=False, home_goals=None, away_goals=None, status=None):
    """Geçmiş ve Telegram için ortak sonuç / iptal / bekleme kuralı."""
    if completed and home_goals is not None and away_goals is not None:
        hit = outcome(market, home_goals, away_goals)
        return "pending" if hit is None else "won" if hit else "lost"
    start = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
    if any(s in (status or "").lower() for s in VOID_STATUSES) and now > start + timedelta(days=1):
        return "void"
    return "void" if now > start + timedelta(days=VOID_AFTER_DAYS) else "pending"
