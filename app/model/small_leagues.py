"""Piyasa öncelikli tahmin görünümü, zayıf veri için açık düşük güven."""
from .blend import devig
from .predict import markets as make_markets, score_matrix


def predict_event(event: dict) -> dict:
    odds = event["iddaa_odds"]
    implied = devig([odds.get(k) for k in ("1", "X", "2")])
    lh, la = 1.35, 1.15
    markets = make_markets(score_matrix(lh, la))["markets"]
    probs = implied or [markets[k]["p"] for k in ("1", "X", "2")]
    p1, px, p2 = probs
    for key, prob in zip(("1", "X", "2"), probs):
        markets[key] = {"p": round(prob, 4), "fair": round(1 / prob, 2), "suggested": round(1 / (prob * 1.05), 2)}
    for key, prob in (("1X", p1 + px), ("12", p1 + p2), ("X2", px + p2)):
        markets[key] = {"p": round(prob, 4), "fair": round(1 / prob, 2), "suggested": round(1 / (prob * 1.05), 2)}
    return {**event, "markets": markets, "iddaa_odds": odds, "lambda_home": lh, "lambda_away": la,
            "pick": None, "confidence": 0.2, "confidence_label": "Düşük", "data_quality": 0.1,
            "blend": {"applied": bool(implied), "weight": 1 if implied else 0,
                      "groups": ["1x2"] if implied else []}}
