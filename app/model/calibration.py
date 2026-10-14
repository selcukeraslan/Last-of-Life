"""Pazar bazlı Platt kalibrasyonu: logit(p') = a·logit(p) + b.

Katsayılar `python -m app.model.pick_backtest --fit` ile walk-forward örneklerden (yalnız maç öncesi
veriyle üretilen olasılıklar) bulunur. Yalnız log-loss'u zaman bölünmüş test diliminde iyileştirenler
tutuldu (diğer pazarlar zaten kalibre: 1X2, Ü1.5, handikap). Alt (A) pazarlar üstün tamamlayıcısıdır
(1 - p'), böylece Alt/Üst ve KG çiftleri 1'e tamamlanmaya devam eder. Piyasa oranı varsa kalibrasyondan
sonra piyasayla harmanlama (blend.py) yapılır.
"""
import math

# pazar -> (a, b); tamamlayıcı: Alt/Yok pazarı
PLATT = {
    "Ü2.5": (1.159, 0.007),
    "Ü3.5": (1.197, 0.154),
    "KG Var": (0.472, 0.135),
    "Ev 0.5Ü": (1.125, -0.078),
    "Dep 0.5Ü": (0.816, 0.209),
}
COMPLEMENT = {"Ü2.5": "A2.5", "Ü3.5": "A3.5", "KG Var": "KG Yok"}


def _logit(p: float) -> float:
    p = min(0.999, max(0.001, p))
    return math.log(p / (1 - p))


def platt(p: float, a: float, b: float) -> float:
    return 1 / (1 + math.exp(-(a * _logit(p) + b)))


def calibrate_p(market: str, p: float) -> float:
    ab = PLATT.get(market)
    return platt(p, *ab) if ab else p


def calibrate_markets(markets: dict) -> dict:
    """{pazar: {p, ...}} -> kalibre pazarlar (p/fair/suggested yeniden hesaplanır, `raw_p` eklenir)."""
    from . import predict as P
    out = dict(markets)
    for market, ab in PLATT.items():
        item = markets.get(market)
        if not item or item.get("p") is None:
            continue
        p = platt(item["p"], *ab)
        out[market] = {**P.odds(p), **{k: v for k, v in item.items() if k not in ("p", "fair", "suggested")},
                       "raw_p": item["p"]}
        other = COMPLEMENT.get(market)
        if other and markets.get(other) and markets[other].get("p") is not None:
            out[other] = {**P.odds(1 - p), **{k: v for k, v in markets[other].items()
                                              if k not in ("p", "fair", "suggested")},
                          "raw_p": markets[other]["p"]}
    return out
