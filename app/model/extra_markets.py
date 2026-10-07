"""Score-matrix probabilities for the extra football markets on the iddaa bulletin."""
import re

from ..config import MODEL
from . import predict as P

_HANDICAP = re.compile(r"^Handikap (-?\d+(?:\.\d+)?) ([1X2])$")
_HALF_TOTAL = re.compile(r"^İY [AÜ](\d+(?:\.\d+)?)$")


def _result(home: int, away: int) -> str:
    return "1" if home > away else "2" if home < away else "X"


def _out(p: float) -> dict:
    return {**P.odds(p), "model_available": True}


def for_match(lambda_home: float, lambda_away: float, iddaa_odds: dict | None = None) -> dict:
    """Return modelled first-half/handicap markets and unmodelled corner/card quote slots."""
    share = MODEL["first_half_goal_share"]
    first = P.score_matrix(lambda_home * share, lambda_away * share)
    second = P.score_matrix(lambda_home * (1 - share), lambda_away * (1 - share))
    result = {f"İY {r}": 0.0 for r in ("1", "X", "2")}
    result.update({f"İY/MS {a}/{b}": 0.0 for a in ("1", "X", "2") for b in ("1", "X", "2")})
    half_totals = {}
    handis = {}
    for line in (iddaa_odds or {}):
        match = _HALF_TOTAL.match(line)
        if match:
            half_totals[match.group(1)] = None
        match = _HANDICAP.match(line)
        if match:
            handis.setdefault(match.group(1), {})
    for line in half_totals:
        result[f"İY A{line}"] = 0.0
        result[f"İY Ü{line}"] = 0.0
    for line in handis:
        for outcome in ("1", "X", "2"):
            result[f"Handikap {line} {outcome}"] = 0.0

    for hi, row in enumerate(first):
        for ai, ph in enumerate(row):
            half_result = _result(hi, ai)
            result[f"İY {half_result}"] += ph
            half_goals = hi + ai
            for line in half_totals:
                threshold = float(line)
                result[f"İY A{line}"] += ph * (half_goals < threshold)
                result[f"İY Ü{line}"] += ph * (half_goals > threshold)
            for hj, row2 in enumerate(second):
                for aj, ps in enumerate(row2):
                    probability = ph * ps
                    full_result = _result(hi + hj, ai + aj)
                    result[f"İY/MS {half_result}/{full_result}"] += probability
                    for line in handis:
                        handicap_result = _result(hi + hj + float(line), ai + aj)
                        result[f"Handikap {line} {handicap_result}"] += probability

    out = {key: _out(probability) for key, probability in result.items()}
    for key in (iddaa_odds or {}):
        if key.startswith(("Korner ", "Kart ")):
            out[key] = {"p": None, "fair": None, "suggested": None, "model_available": False}
    return out
