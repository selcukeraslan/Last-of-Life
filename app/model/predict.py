"""Skor dağılımı (Dixon-Coles düzeltmeli Poisson) ve bahis pazarları."""
import math

from ..config import MODEL

MAX_GOALS = 10


def _pois(k: int, lam: float) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def score_matrix(lh: float, la: float, rho: float | None = None) -> list[list[float]]:
    rho = MODEL["dc_rho"] if rho is None else rho
    ph = [_pois(i, lh) for i in range(MAX_GOALS + 1)]
    pa = [_pois(j, la) for j in range(MAX_GOALS + 1)]
    mat = [[ph[i] * pa[j] for j in range(MAX_GOALS + 1)] for i in range(MAX_GOALS + 1)]
    # Dixon-Coles: düşük skorlu sonuçlar arasındaki bağımlılık düzeltmesi
    mat[0][0] *= 1 - lh * la * rho
    mat[0][1] *= 1 + lh * rho
    mat[1][0] *= 1 + la * rho
    mat[1][1] *= 1 - rho
    tot = sum(map(sum, mat))
    return [[v / tot for v in row] for row in mat]


def odds(p: float, margin: float | None = None) -> dict:
    margin = MODEL["margin"] if margin is None else margin
    if p <= 0:
        return {"p": 0.0, "fair": None, "suggested": None}
    fair = 1 / p
    sug = max(1.01, 1 / min(0.99, p * (1 + margin)))
    return {"p": round(p, 4), "fair": round(fair, 2), "suggested": round(sug, 2)}


def markets(mat: list[list[float]]) -> dict:
    n = len(mat)
    p1 = sum(mat[i][j] for i in range(n) for j in range(n) if i > j)
    px = sum(mat[i][i] for i in range(n))
    p2 = 1 - p1 - px
    tot = lambda f: sum(mat[i][j] for i in range(n) for j in range(n) if f(i, j))
    out = {
        "1": odds(p1), "X": odds(px), "2": odds(p2),
        "1X": odds(p1 + px), "12": odds(p1 + p2), "X2": odds(px + p2),
        "Ü1.5": odds(tot(lambda i, j: i + j >= 2)), "A1.5": odds(tot(lambda i, j: i + j <= 1)),
        "Ü2.5": odds(tot(lambda i, j: i + j >= 3)), "A2.5": odds(tot(lambda i, j: i + j <= 2)),
        "Ü3.5": odds(tot(lambda i, j: i + j >= 4)), "A3.5": odds(tot(lambda i, j: i + j <= 3)),
        "KG Var": odds(tot(lambda i, j: i > 0 and j > 0)), "KG Yok": odds(tot(lambda i, j: i == 0 or j == 0)),
        "Ev 0.5Ü": odds(tot(lambda i, j: i >= 1)), "Dep 0.5Ü": odds(tot(lambda i, j: j >= 1)),
    }
    scores = sorted(((mat[i][j], f"{i}-{j}") for i in range(n) for j in range(n)), reverse=True)[:6]
    out_scores = [{"score": s, **odds(p)} for p, s in scores]
    return {"markets": out, "scores": out_scores}


# --- Güven ----------------------------------------------------------------------
# Kaynak: sürekli 0-1 skor. Skor = min(önerinin olasılığından, veri kapsamından gelen skor).
# Etiket ve açıklama bu skordan türetilir (eşikler: 0.45 Orta, 0.70 Yüksek), böylece
#   olasılık >= %62 Yüksek, %56-62 Orta, altı Düşük; ağırlıklı maç < 12 en fazla Orta, < 8 Düşük.
CONF_LABELS = ["Düşük", "Orta", "Yüksek"]
CONF_CUTS = (0.45, 0.70)
CONF_P = (0.33, 0.56, 0.62, 0.80)      # olasılık düğümleri -> skor 0, 0.45, 0.70, 1
CONF_DATA = (0.0, 8.0, 12.0, 20.0)     # ağırlıklı maç düğümleri -> skor 0, 0.45, 0.70, 1
CONF_RULE = ("Güven, önerinin olasılığına göre verilir (%62 ve üstü Yüksek, %56–62 Orta, altı Düşük); "
             "takımlardan biri için yeterli maç verisi yoksa etiket bir ya da iki kademe sınırlanır.")


def _ramp(x: float, knots: tuple) -> float:
    ys = (0.0, CONF_CUTS[0], CONF_CUTS[1], 1.0)
    if x <= knots[0]:
        return 0.0
    for i in range(1, 4):
        if x <= knots[i]:
            return ys[i - 1] + (ys[i] - ys[i - 1]) * (x - knots[i - 1]) / (knots[i] - knots[i - 1])
    return 1.0


def confidence_label(level: float) -> str:
    return CONF_LABELS[(level >= CONF_CUTS[0]) + (level >= CONF_CUTS[1])]


def confidence(p: float | None, n_min: float) -> dict:
    """p: önerilen pazarın olasılığı (öneri yoksa None), n_min: iki takımdan az olanın (zaman ağırlıklı) maç sayısı."""
    if p is None:
        return {"confidence": 0.0, "confidence_label": "Düşük",
                "confidence_reason": "belirgin bir öneri yok"}
    by_p, by_n = _ramp(p, CONF_P), _ramp(n_min, CONF_DATA)
    level = math.floor(min(by_p, by_n) * 100 + 1e-9) / 100  # aşağı yuvarla: etiket eşiği geçmeden Orta/Yüksek olmasın
    label = confidence_label(level)
    if by_n < by_p and confidence_label(by_n) != confidence_label(by_p):
        reason = f"olasılık %{p * 100:.0f}, ama veri az (~{n_min:.0f} maç) olduğu için sınırlandı"
    elif n_min >= CONF_DATA[2]:
        reason = f"olasılık %{p * 100:.0f}, veri yeterli (~{n_min:.0f} maç)"
    else:
        reason = f"olasılık %{p * 100:.0f} (~{n_min:.0f} maç veri)"
    return {"confidence": level, "confidence_label": label, "confidence_reason": reason}


# Öneri üretirken bakılan pazarlar ve kısa açıklamaları
# (A3.5 / Ü1.5 gibi neredeyse her maçta tutan, düşük bilgili pazarlar bilerek yok)
PICK_MARKETS = ["1", "X", "2", "1X", "X2", "Ü2.5", "A2.5", "KG Var", "KG Yok"]


def best_pick(mk: dict, min_odds: float = 1.40) -> dict | None:
    """En olası ama anlamlı orana sahip pazarı seç (çok düşük oranlı 'bedava' tahminleri ele)."""
    best = None
    for key in PICK_MARKETS:
        o = mk[key]
        if o["suggested"] is None or o["suggested"] < min_odds:
            continue
        if best is None or o["p"] > best[1]["p"]:
            best = (key, o)
    if not best:
        return None
    return {"market": best[0], **best[1]}
