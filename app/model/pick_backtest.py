"""Pazar bazlı, zaman güvenli (walk-forward) geri test: her maç yalnız öncesindeki veriyle tahmin edilir.

Çıktı: pazar başına tahmin edilen olasılık dilimlerinde gerçekleşme oranı (kalibrasyon), tutma oranı ve
ROI. Oran olarak varsa kaydedilmiş iddaa oranı (odds_log), yoksa modelin önerdiği oran (adil oran + %5
marj) kullanılır; ikinci durumda ROI kalibrasyonu ölçer (iyi kalibre modelde ≈ -%4.8).

Kullanım:  python -m app.model.pick_backtest [--step 2] [--out sonuc.json]
Seçici kuralları (`picks.py`) bu örnekler üzerinde eski ve yeni haliyle karşılaştırır.
"""
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor

from ..config import LEAGUES, MODEL, is_cup
from ..db import session
from . import extra_markets, predict as P
from .coupon_history import pick_result
from .engine import LeagueModel, _load
from .ratings import Elo, Strengths

HANDICAP_LINES = (-2, -1, 1, 2)


def full_probs(base: LeagueModel, m: dict, hist, st, elo) -> dict:
    """Bir maç için modelin tüm skorla çözülebilir pazar olasılıkları (düz p; harman/kalibrasyon yok)."""
    pred = base.predict(m["home"], m["away"], m["ts"], strengths=st, elo=elo, history=hist, news={}, detail=False, calibrate=False)
    probs = {k: v["p"] for k, v in pred["markets"].items()}
    mat = P.score_matrix(pred["lambda_home"], pred["lambda_away"])
    for line in HANDICAP_LINES:
        for r, p in extra_markets.handicap_probs(mat, float(line)).items():
            probs[f"Handikap {line} {r}"] = p
    probs["lambda_home"], probs["lambda_away"] = pred["lambda_home"], pred["lambda_away"]
    return probs


def league_samples(league: str, step: int = 1, min_history: int | None = None) -> list[dict]:
    with session() as conn:
        done, _ = _load(conn, league)
    if min_history is None:
        min_history = 380  # ~1 sezon ısınma
    if len(done) <= min_history:
        return []
    base = LeagueModel(league, [], [], {})
    elo = Elo()
    for m in done[:min_history]:
        elo.update(m)
    out = []
    for idx in range(min_history, len(done), step):
        m = done[idx]
        hist = done[:idx]
        probs = full_probs(base, m, hist, Strengths(hist, m["ts"]), elo)
        out.append({"league": league, "id": m["id"], "day": m["kickoff"][:10], "probs": probs,
                    "hg": m["home_goals"], "ag": m["away_goals"]})
        for k in range(idx, min(idx + step, len(done))):
            elo.update(done[k])
    return out


def collect(step: int = 2) -> list[dict]:
    leagues = [lg for lg in LEAGUES if not is_cup(lg)]
    with ProcessPoolExecutor() as pool:
        parts = pool.map(league_samples, leagues, [step] * len(leagues))
    return [s for part in parts for s in part]


def family(market: str) -> str:
    if market in ("1", "X", "2"):
        return "1X2"
    if market in ("1X", "12", "X2"):
        return "Çifte şans"
    if market.startswith("Handikap"):
        return "Handikap"
    if market.startswith(("Ü", "A")):
        return "Alt/Üst " + market[1:]
    if market.startswith("KG"):
        return "KG"
    return "Takım golü"


def bucket_table(rows: list[tuple[float, float, bool]], edges=(0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01)) -> list[dict]:
    out = []
    for lo, hi in zip(edges, edges[1:]):
        part = [r for r in rows if lo <= r[0] < hi]
        if part:
            n = len(part)
            out.append({"lo": lo, "hi": min(hi, 1.0), "n": n, "predicted": round(sum(r[0] for r in part) / n, 4),
                        "actual": round(sum(r[2] for r in part) / n, 4),
                        "roi": round(sum(r[1] * r[2] for r in part) / n - 1, 4)})
    return out


def market_report(samples: list[dict], prob_of=lambda s, mk: s["probs"].get(mk)) -> dict:
    """Pazar -> p dilimlerine göre kalibrasyon/ROI (oran = model önerilen oranı)."""
    rows: dict[str, list] = {}
    for s in samples:
        for mk in s["probs"]:
            if mk.startswith("lambda"):
                continue
            res = pick_result(mk, s["hg"], s["ag"])
            p = s["probs"][mk]
            if res is None or not 0 < p < 1:
                continue
            odds = max(1.01, 1 / min(0.99, p * (1 + MODEL["margin"])))
            rows.setdefault(mk, []).append((p, odds, res == "won"))
    return {mk: bucket_table(r) for mk, r in sorted(rows.items())}


if __name__ == "__main__":
    step = int(sys.argv[sys.argv.index("--step") + 1]) if "--step" in sys.argv else 2
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "pick_backtest_samples.json"
    data = collect(step)
    with open(out, "w") as f:
        json.dump(data, f)
    print(f"{len(data)} örnek -> {out}")
