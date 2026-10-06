"""Avrupa kupaları (Şampiyonlar Ligi / Avrupa Ligi) için ligler arası güç modeli.

Sorun: her ligin Elo/Poisson güçleri kendi içinde 1500 etrafında ortalanır; Ajax'ın 1600'ü ile Fenerbahçe'nin
1600'ü aynı anlama gelmez. Çözüm üç adımdır:

  1. Taban güç = takımın kendi liginin Elo'su + lig ofseti. Ofset, lig güç önselinden (UEFA ülke sırası /
     ClubElo lig ortalamalarına dayanan yaklaşık değerler) başlar.
  2. Ofsetler, iki kupanın tamamlanmış ligler arası maçlarından öğrenilir: lojistik Elo kaybı + önsele L2
     büzülme, köşegen Newton adımlarıyla (MAP). Veri azsa önsele yakın kalır.
  3. Takıma özel kupa düzeltmesi: kupa maçları kronolojik Elo güncellemesiyle taban güce eklenir. Ligi bizde
     olmayan takımlar ("diğer": Celtic, Club Brugge, Kairat...) 1500 + "diğer" ofsetiyle başlar ve daha
     büyük K ile kupa sonuçlarından öğrenir.

Skor modeli aynı `LeagueModel.predict` hattıdır; yalnız Elo yerine ligler arası güç kullanılır, Poisson
güçleri yalnızca kupa maçlarından (küçük örnek, yüksek büzülme) hesaplanır ve Elo ağırlığı yükseltilir.
"""
import math
from collections import defaultdict
from datetime import datetime, timezone

from ..config import LEAGUES, MODEL, is_cup
from ..db import session
from . import engine
from .engine import LeagueModel

# Ortak ölçekte lig ortalama takım gücü ofseti (Elo puanı). Elle seçilmiş yaklaşık değerler; veriyle güncellenir.
LEAGUE_PRIOR = {
    "eng.1": 200.0, "esp.1": 150.0, "ita.1": 130.0, "ger.1": 110.0, "fra.1": 60.0,
    "por.1": 10.0, "ned.1": 10.0, "tur.1": -50.0, "tur.2": -170.0,
}
OTHER = "other"  # ligi kapsamımızda olmayan takımlar
OTHER_PRIOR = 0.0
PRIOR_SD = 60.0  # önselin standart sapması (Elo puanı)
NEWTON_ITERS = 30
CUP_K_KNOWN = 12.0  # kendi ligi bilinen takımın kupa sonucundan öğrenme hızı
CUP_K_UNKNOWN = 24.0
CUP_ELO_WEIGHT = 0.85  # kupa Poisson örneği küçük: Elo'ya daha çok güven
_C = math.log(10) / 400


def _expected(diff: float) -> float:
    return 1 / (1 + 10 ** (-diff / 400))


def _score(gf: int, ga: int) -> float:
    return 1.0 if gf > ga else 0.5 if gf == ga else 0.0


def fit_offsets(games: list[tuple], prior: dict[str, float], sd: float = PRIOR_SD) -> dict[str, float]:
    """games: (ev_taban_güç, ev_lig, dep_taban_güç, dep_lig, ev_skoru). Lig ofsetlerini MAP ile tahmin eder."""
    off = dict(prior)
    adv = MODEL["elo_home_adv"]
    for _ in range(NEWTON_ITERS):
        grad, hess = defaultdict(float), defaultdict(float)
        for hr, hl, ar, al, s in games:
            if hl == al:
                continue  # aynı lig: ofset farkı değiştirmez
            e = _expected(hr + off[hl] + adv - ar - off[al])
            grad[hl] += e - s
            grad[al] -= e - s
            hess[hl] += e * (1 - e)
            hess[al] += e * (1 - e)
        for lg in off:
            g = _C * grad[lg] + (off[lg] - prior[lg]) / sd ** 2
            h = _C ** 2 * hess[lg] + 1 / sd ** 2
            off[lg] -= 0.7 * g / h  # sönümlü adım
    return off


class CupElo:
    """`Elo` ile aynı arayüz (get/expected); takım adından ligler arası gücü verir."""

    def __init__(self, ratings: dict[str, float], default: float):
        self.r = ratings
        self.default = default

    def get(self, team: str) -> float:
        return self.r.get(team, self.default)

    def expected(self, home: str, away: str) -> float:
        return _expected(self.get(home) + MODEL["elo_home_adv"] - self.get(away))


def build_ratings(cup_done: list[dict], team_info: dict[str, tuple[str, float]], extra_names: dict[str, str]):
    """team_info: takım kimliği -> (lig, ligi içi Elo). Dönen: (ad->güç, ofsetler, takım başı kupa düzeltmesi)."""
    def base(tid):
        lg, rating = team_info.get(tid, (OTHER, 1500.0))
        return lg, rating

    prior = {**LEAGUE_PRIOR, OTHER: OTHER_PRIOR}
    games = []
    for m in cup_done:
        hl, hr = base(m["home_id"])
        al, ar = base(m["away_id"])
        games.append((hr, hl, ar, al, _score(m["home_goals"], m["away_goals"])))
    off = fit_offsets(games, prior)

    adj: dict[str, float] = defaultdict(float)
    for m in sorted(cup_done, key=lambda x: x["ts"]):
        (hl, hr), (al, ar) = base(m["home_id"]), base(m["away_id"])
        h, a = m["home_id"], m["away_id"]
        e = _expected(hr + off[hl] + adj[h] + MODEL["elo_home_adv"] - ar - off[al] - adj[a])
        gf, ga = m["home_goals"], m["away_goals"]
        mult = math.log(abs(gf - ga) + 1) + 1 if gf != ga else 1.0
        delta = mult * (_score(gf, ga) - e)
        adj[h] += (CUP_K_UNKNOWN if hl == OTHER else CUP_K_KNOWN) * delta
        adj[a] -= (CUP_K_UNKNOWN if al == OTHER else CUP_K_KNOWN) * delta

    ratings = {}
    for tid, name in extra_names.items():
        lg, rating = base(tid)
        ratings[name] = rating + off[lg] + adj.get(tid, 0.0)
    return ratings, off, dict(adj)


class CupModel(LeagueModel):
    """Elo yerine ligler arası güç kullanan `LeagueModel`; tahmine `cross_league` şeffaflık alanı ekler."""
    elo_weight = CUP_ELO_WEIGHT
    offsets: dict = {}
    cross: dict = {}

    def predict(self, home, away, kickoff, **kw):
        out = super().predict(home, away, kickoff, **kw)
        if "factors" in out:
            out["factors"]["cross_league"] = {
                "home": self.cross.get(home), "away": self.cross.get(away), "league_offsets": self.offsets}
        return out


def build_cup_model(league: str) -> CupModel:
    """Kupa için `LeagueModel` alt sınıfı kurar (engine.get_model tarafından çağrılır)."""
    domestic = {lg: engine.get_model(lg) for lg in LEAGUES if not is_cup(lg)}
    team_info: dict[str, tuple[str, float]] = {}
    domestic_name: dict[str, tuple[str, str]] = {}
    for lg, model in domestic.items():
        for m in (*model.done, *model.upcoming):
            for tid, name in ((m["home_id"], m["home"]), (m["away_id"], m["away"])):
                if tid and tid not in team_info:
                    team_info[tid] = (lg, model.elo.get(name))
                    domestic_name[tid] = (lg, name)

    cup_done, own_done, own_upcoming, names = [], [], [], {}
    now = datetime.now(timezone.utc)
    news_by_league = {}
    with session() as conn:
        for cup in (c for c in LEAGUES if is_cup(c)):
            done, upcoming = engine._load(conn, cup)
            cup_done += done
            for m in (*done, *upcoming):
                names[m["home_id"]] = m["home"]
                names[m["away_id"]] = m["away"]
            if cup == league:
                own_done, own_upcoming = done, upcoming
        for lg in domestic:
            news_by_league[lg] = engine.news_scores(conn, lg, now)

    ratings, offsets, adj = build_ratings(cup_done, team_info, names)
    other_default = 1500.0 + offsets[OTHER]

    news = {}
    for tid, name in names.items():
        if tid in domestic_name:
            lg, dn = domestic_name[tid]
            if dn in news_by_league[lg]:
                news[name] = news_by_league[lg][dn]
    model = CupModel(league, own_done, own_upcoming, news)
    model.elo = CupElo(ratings, other_default)
    model.offsets = {k: round(v) for k, v in offsets.items()}
    model.cross = {names[t]: {"league": team_info.get(t, (OTHER, 0))[0],
                              "domestic_elo": round(team_info[t][1]) if t in team_info else None,
                              "cup_adj": round(adj.get(t, 0.0), 1)} for t in names}
    cup_n = dict(model.strengths.n_weighted)
    for tid, name in names.items():  # güven puanı: yerel lig maç sayısı da veri sayılır
        if tid in domestic_name:
            lg, dn = domestic_name[tid]
            cup_n[name] = cup_n.get(name, 0.0) + domestic[lg].strengths.n_weighted.get(dn, 0.0)
    model.strengths.n_weighted = cup_n
    return model
