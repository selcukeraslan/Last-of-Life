"""Eski (main) ve yeni seçim mantığını aynı geçmiş günlerde karşılaştırır (walk-forward örnekler üzerinde).

  python -m app.model.pick_backtest --step 1 --out /tmp/samples.json
  git archive <eski-commit> app | tar -x -C /tmp/legacy
  PYTHONPATH=/tmp/legacy python scripts/compare_picks.py /tmp/samples.json legacy > /tmp/legacy.json
  python scripts/compare_picks.py /tmp/samples.json new > /tmp/new.json

Sentetik defter: iddaa oranı = 1/(ham model olasılığı x 1.07). Gerçek iddaa geçmişi (odds_log) bu ortamda
yoktur; bu yüzden ROI "modele karşı adil defter" ROI'sidir (-%7 civarı beklenir) ve asıl ölçü, seçilen
pazarların gerçek tutma oranı ile pazar dağılımıdır. "legacy" modunda eski kod, işareti ters handikap
olasılığıyla çalıştırılır (hata, eski sürümde canlıydı).
"""
import json
import math
import sys
from collections import Counter, defaultdict

MARGIN = 1.07
LINES = (-2, -1, 1, 2)
HANDICAPS = [f"Handikap {l} {r}" for l in LINES for r in "1X2"]


def build_entry(i, day, probs, legacy, cp, calibrate):
    base = {k: v for k, v in probs.items() if not k.startswith(("Handikap", "lambda"))}
    hand = {}
    for k in HANDICAPS:
        line, r = k.split()[1], k.split()[2]
        src = f"Handikap {-int(line)} {r}" if legacy else k  # eski kod çizgiyi deplasmana ekliyordu
        hand[k] = probs[src]
    book = {k: round(max(1.01, 1 / (min(0.99, probs[k]) * MARGIN)), 2) for k in list(base) + HANDICAPS}
    cal = (lambda m, p: p) if not calibrate else __import__("app.model.calibration", fromlist=["x"]).calibrate_p

    def item(k, p):
        p = cal(k, p)
        return {"p": p, "fair": round(1 / p, 2), "suggested": book[k]}
    pred = {"id": f"{i}", "league": "x", "kickoff": day, "home": "h", "away": "a",
            "markets": {k: item(k, p) for k, p in base.items()},
            "extra_markets": {k: item(k, p) for k, p in hand.items()}}
    return pred, cp._choices(pred, book), book


def _pick_result(market, h, a):
    """coupon_history.pick_result'ın kopyası (eski kod çözümünde de çalışsın diye)."""
    import re
    rules = {"1": h > a, "X": h == a, "2": h < a, "1X": h >= a, "12": h != a, "X2": h <= a,
             "KG Var": h > 0 and a > 0, "KG Yok": h == 0 or a == 0, "Ev 0.5Ü": h >= 1, "Dep 0.5Ü": a >= 1}
    if market in rules:
        return "won" if rules[market] else "lost"
    if m := re.match(r"^([ÜA])(\d\.\d)$", market):
        t, line = h + a, float(m.group(2))
        return "won" if (t > line if m.group(1) == "Ü" else t < line) else "lost"
    if m := re.match(r"^Handikap (-?\d+) ([1X2])$", market):
        d = h + float(m.group(1)) - a
        return "won" if {"1": d > 0, "X": d == 0, "2": d < 0}[m.group(2)] else "lost"


def settle(pick, s, pick_result):
    return pick_result(pick["market"], s["hg"], s["ag"]) == "won"


def main(path, mode):
    from app.model import coupons as cp
    pick_result = _pick_result
    legacy = mode == "legacy"
    samples = json.load(open(path))
    by_day = defaultdict(list)
    for s in samples:
        by_day[s["day"]].append(s)
    stats = {k: {"coupons": 0, "won": 0, "legs": 0, "legs_won": 0, "stake": 0, "ret": 0.0,
                 "markets": Counter(), "hit": Counter(), "ret_m": defaultdict(float)} for k in ("banko", "surprise")}
    for day, rows in sorted(by_day.items()):
        if len(rows) < 3:
            continue
        entries, truth = [], {}
        for n, s in enumerate(rows):
            p, ch, book = build_entry(f"{day}-{n}", day, s["probs"], legacy, cp, calibrate=not legacy)
            entries.append((p, ch))
            truth[p["id"]] = (s, book)
        for kind, picks in (("banko", cp.select_banko(entries)), ("surprise", cp.select_surprise(entries))):
            if not picks:
                continue
            st = stats[kind]
            st["coupons"] += 1
            won_all, odds = True, 1.0
            for pick in picks:
                s, book = truth[pick["id"]]
                # eski sürümde "Handikap L r" etiketi iddaa'nın gerçek pazarına yazılır; gerçek sonuç etikete göre
                ok = settle(pick, s, pick_result)
                st["legs"] += 1; st["legs_won"] += ok
                st["markets"][pick["market"].split()[0] if pick["market"].startswith("Handikap") else pick["market"]] += 1
                st["hit"][pick["market"].split()[0] if pick["market"].startswith("Handikap") else pick["market"]] += ok
                won_all &= ok
                odds *= book[pick["market"]]
            st["won"] += won_all
            st["stake"] += 1
            st["ret"] += odds if won_all else 0
    out = {}
    for kind, st in stats.items():
        out[kind] = {"coupons": st["coupons"], "coupon_hit": round(st["won"] / max(1, st["coupons"]), 4),
                     "leg_hit": round(st["legs_won"] / max(1, st["legs"]), 4),
                     "roi": round(st["ret"] / max(1, st["stake"]) - 1, 4),
                     "market_share": {m: round(n / st["legs"], 3) for m, n in st["markets"].most_common(8)},
                     "market_leg_hit": {m: round(st["hit"][m] / n, 3) for m, n in st["markets"].most_common(8)}}
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
