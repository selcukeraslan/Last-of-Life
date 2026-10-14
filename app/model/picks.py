"""Pazar seçim kuralları: kalibre olasılık + iddaa oranına göre değer, çeşitlendirme.

Eski kural yalnız "en yüksek EV" (p·oran-1) veya "en yüksek p" seçiyordu. Model-piyasa farkını
maksimize etmek, modelin en yanlış olduğu uç pazarları (tersine işaretli handikap, düşük olasılıklı
yüksek oranlı Ü3.5) seçmek demektir (winner's curse). Yeni skor:

    skor = p + 0.6·(p - taban_oran) + 0.8·clip(EV, -0.10, +0.15) - 0.06·max(0, oran - 2.5)

yani olasılık ana terim; pazarın koşulsuz taban oranına göre "lift" (modelin takıma özel bilgisi,
Ev 0.5Ü ~%78 her maçta tuttuğu için bilgisizdir) ikinci terim; değer sınırlı bir bonus; yüksek oran cezalıdır. Maç başına en az MIN_P
olasılık ve MIN_ODDS oran gerekir; aynı gün aynı pazar ailesi tekrar seçildikçe skordan ceza düşer ve
aile başına üst sınır (CAP_SHARE) vardır, böylece tek bir pazar listeyi domine edemez.
"""
import math
import re

MIN_P = 0.55
MIN_ODDS = 1.35  # altında "bedava" pazar; Ü1.5 / A3.5 de bilgisiz sayılır (aşağıda)
EV_FLOOR, EV_CAP = -0.10, 0.15
EV_WEIGHT = 0.8
LIFT_WEIGHT = 0.6
# Pazarın koşulsuz tutma oranı (5 ligde ~8.7 bin walk-forward maç; python -m app.model.pick_backtest)
BASE_RATE = {
    "1": 0.442, "X": 0.251, "2": 0.307, "1X": 0.693, "12": 0.749, "X2": 0.558,
    "Ü1.5": 0.775, "A1.5": 0.225, "Ü2.5": 0.54, "A2.5": 0.46, "Ü3.5": 0.312, "A3.5": 0.688,
    "KG Var": 0.547, "KG Yok": 0.453, "Ev 0.5Ü": 0.776, "Dep 0.5Ü": 0.708,
    "Handikap -2 1": 0.104, "Handikap -2 X": 0.122, "Handikap -2 2": 0.774,
    "Handikap -1 1": 0.226, "Handikap -1 X": 0.216, "Handikap -1 2": 0.558,
    "Handikap 1 1": 0.693, "Handikap 1 X": 0.165, "Handikap 1 2": 0.142,
    "Handikap 2 1": 0.858, "Handikap 2 X": 0.085, "Handikap 2 2": 0.057,
}
HIGH_ODDS, HIGH_ODDS_PENALTY = 2.5, 0.06
REPEAT_PENALTY = 0.04
CAP_SHARE = 0.40
MIN_CAP = 2

# Otomatik seçilebilen aileler. İY / İY-MS bilinçli yok: maçlar tablosunda devre skoru tutulmadığından
# sonuçlandırılamaz (Model Karnesi'nde doğrulanamayan seçim olurdu).
FAMILIES = ("1X2", "Çifte şans", "Gol", "KG", "Handikap", "Takım golü")
TRIVIAL = {"Ü1.5", "A3.5"}  # her maçta ~%75: yalnız Banko'da (allow_trivial) aday olur
_REDUNDANT = {"Handikap 1 1", "Handikap -1 2"}  # sırasıyla 1X ve X2 ile aynı
_TEAM_TOTAL = re.compile(r"^(Ev|Dep) 0\.5Ü$")


def family(market: str) -> str | None:
    if market in ("1", "X", "2"):
        return "1X2"
    if market in ("1X", "12", "X2"):
        return "Çifte şans"
    if market.startswith("Handikap "):
        return None if market in _REDUNDANT else "Handikap"
    if re.match(r"^[ÜA]\d\.\d$", market):
        return "Gol"
    if market.startswith("KG "):
        return "KG"
    if _TEAM_TOTAL.match(market):
        return "Takım golü"
    return None


def score(p: float, odds: float, market: str = "") -> float:
    ev = max(EV_FLOOR, min(EV_CAP, p * odds - 1))
    lift = LIFT_WEIGHT * (p - BASE_RATE[market]) if market in BASE_RATE else 0.0
    return p + lift + EV_WEIGHT * ev - HIGH_ODDS_PENALTY * max(0.0, odds - HIGH_ODDS)


def eligible(choices: list[dict], min_p: float = MIN_P, min_odds: float = MIN_ODDS,
             max_p: float = 1.0, allow_trivial: bool = False) -> list[dict]:
    return [c for c in choices if family(c["market"]) and min_p <= c["p"] <= max_p and c["odds"] >= min_odds
            and (allow_trivial or c["market"] not in TRIVIAL)]


def best_choice(choices: list[dict], counts: dict[str, int] | None = None, cap: int | None = None,
                **limits) -> dict | None:
    """Maçın en iyi pazarı; `counts` günlük aile kullanımıdır (tekrar cezası, `cap` üst sınır)."""
    best, best_key = None, None
    for c in eligible(choices, **limits):
        fam = family(c["market"])
        used = (counts or {}).get(fam, 0)
        if cap is not None and used >= cap:
            continue
        key = (score(c["p"], c["odds"], c["market"]) - REPEAT_PENALTY * used, c["p"])
        if best_key is None or key > best_key:
            best, best_key = c, key
    return best


def family_cap(total: int) -> int:
    return max(MIN_CAP, math.ceil(CAP_SHARE * total))


def assign(entries: list[tuple[dict, list[dict]]], **limits) -> list[tuple[dict, dict]]:
    """Her maça tek pazar; maçlar ham skoruna göre sıralanıp aile cezası/üst sınırıyla çeşitlendirilir."""
    raw = [(p, best_choice(ch, **limits)) for p, ch in entries]
    raw = [(p, c, ch) for (p, c), (_, ch) in zip(raw, entries) if c]
    raw.sort(key=lambda x: -score(x[1]["p"], x[1]["odds"], x[1]["market"]))
    cap, counts, out = family_cap(len(raw)), {}, []
    for p, _, ch in raw:
        # Üst sınır yumuşaktır: başka aileden uygun pazar yoksa maç yine de en iyi pazarını alır
        c = best_choice(ch, counts, cap, **limits) or best_choice(ch, counts, **limits)
        if c:
            counts[family(c["market"])] = counts.get(family(c["market"]), 0) + 1
            out.append((p, c))
    return out


def repeat_factor(picks: list[dict]) -> float:
    """Kombinasyonda aynı aileden tekrar eden her seçim için çarpan (0.92^tekrar)."""
    fams = [family(p["market"]) for p in picks]
    return 0.92 ** (len(fams) - len(set(fams)))
