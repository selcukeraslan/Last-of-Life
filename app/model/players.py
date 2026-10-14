"""Oyuncu gol atar (anytime scorer) olasılıkları.

Veri: ESPN maç özetlerinden oyuncu bazlı gol/dakika (scrapers/espn_players.py). Yöntem:
  1. Oyuncunun 90 dakika başına gol oranı, mevkisine göre bir öncül (PRIOR_RATE) ve PRIOR_MINUTES
     dakikalık sanal veriyle büzülür: (gol + öncül·K/90) / (dakika/90 + K/90). Az dakikalı oyuncu öncüle yaklaşır.
  2. Beklenen oynama: son RECENT maçta forma payı (p_play) x oynadığı maçlardaki ortalama dakika.
  3. Ham beklenti λ_i = oran90 x dk/90 x p_play, takımın bu maçtaki beklenen golüne (model λ) oranlanarak
     ölçeklenir: λ_i' = λ_takım · SHARE · λ_i / Σλ (takım xG payı; rakip ve form etkisini modelden alır).
  4. P(gol atar) = 1 - exp(-λ_i'); adil oran = 1/P.
Az veri (< LOW_DATA_MINUTES dk veya < LOW_DATA_APPS maç) "Az veri" işaretlenir. Kadro/sakatlık bilgisi
yoktur: p_play son maçlardaki forma payıdır. İddaa oyuncu oranı olmadığı için değer (EV) hesaplanmaz.
"""
import math

from . import predict as P

PRIOR_RATE = {"F": 0.40, "M": 0.12, "D": 0.04, "G": 0.0}  # gol / 90 dk
PRIOR_MINUTES = 450.0
LOW_DATA_MINUTES = 450.0
LOW_DATA_APPS = 5
WINDOW = 30            # oran için bakılan son takım maçı
RECENT = 6             # oynama payı / dakika için son maç
MIN_TEAM_MATCHES = 3   # bu kadar maç verisi yoksa tahmin yok
SHARE = 0.97           # takım golünün oyuncu golü olan payı (kalan: kendi kalesine gol)
MIN_P = 0.03
TOP = 6


def position_group(abbr: str | None) -> str:
    a = (abbr or "").upper().split("-")[0]  # CF-L / CD-R: yan eki at
    if a in ("G", "GK"):
        return "G"
    if a in ("SS", "ST", "CF", "F") or a.endswith("F") or a.startswith("F"):
        return "F"
    if "M" in a:
        return "M"
    return "D"


def estimate(team_matches: list[dict], rows: list[dict], team_lambda: float, top: int = TOP) -> dict:
    """team_matches: [{id}] yeni -> eski (özeti çekilmiş maçlar); rows: bu maçlardaki oyuncu satırları."""
    if len(team_matches) < MIN_TEAM_MATCHES:
        return {"available": False, "matches": len(team_matches), "players": []}
    recent_ids = [m["id"] for m in team_matches[:RECENT]]
    by_player: dict[str, dict] = {}
    for r in rows:  # satırlar yeni -> eski
        p = by_player.setdefault(r["player_id"], {"name": r["name"], "position": r["position"], "minutes": 0.0,
                                                   "goals": 0, "apps": 0, "recent": []})
        p["minutes"] += r["minutes"]
        p["goals"] += r["goals"]
        p["apps"] += 1
        if r["match_id"] in recent_ids:
            p["recent"].append(r["minutes"])
    raw = []
    for p in by_player.values():
        if not p["recent"]:
            continue  # son maçlarda hiç oynamamış: kadro dışı varsay
        group = position_group(p["position"])
        rate90 = (p["goals"] + PRIOR_RATE[group] * PRIOR_MINUTES / 90) / (p["minutes"] / 90 + PRIOR_MINUTES / 90)
        p_play = len(p["recent"]) / len(recent_ids)
        exp_min = sum(p["recent"]) / len(p["recent"])
        raw.append({**p, "group": group, "rate90": rate90, "p_play": p_play, "exp_min": exp_min,
                    "lam": rate90 * exp_min / 90 * p_play})
    total = sum(p["lam"] for p in raw)
    if total <= 0:
        return {"available": False, "matches": len(team_matches), "players": []}
    scale = team_lambda * SHARE / total
    out = []
    for p in raw:
        lam = p["lam"] * scale
        prob = 1 - math.exp(-lam)
        if prob < MIN_P:
            continue
        out.append({"name": p["name"], "position": p["position"], "group": p["group"], **P.odds(prob),
                    "apps": p["apps"], "minutes": round(p["minutes"]), "goals": p["goals"],
                    "rate90": round(p["rate90"], 3), "p_play": round(p["p_play"], 2),
                    "expected_minutes": round(p["exp_min"]),
                    "low_data": p["minutes"] < LOW_DATA_MINUTES or p["apps"] < LOW_DATA_APPS})
    out.sort(key=lambda x: -x["p"])
    return {"available": True, "matches": len(team_matches), "players": out[:top]}


def _team_data(conn, team_id: str, before: str):
    matches = [dict(r) for r in conn.execute(
        "SELECT m.id FROM matches m JOIN player_fetch_log l ON l.match_id=m.id WHERE m.completed=1 AND l.players>0 "
        "AND m.kickoff<? AND (m.home_id=? OR m.away_id=?) ORDER BY m.kickoff DESC LIMIT ?",
        (before, team_id, team_id, WINDOW)).fetchall()]
    if not matches:
        return matches, []
    marks = ",".join("?" for _ in matches)
    rows = [dict(r) for r in conn.execute(
        f"SELECT p.match_id, p.player_id, p.name, p.position, p.minutes, p.goals FROM player_match_stats p "
        f"JOIN matches m ON m.id=p.match_id WHERE p.team_id=? AND p.match_id IN ({marks}) ORDER BY m.kickoff DESC",
        (team_id, *[m["id"] for m in matches])).fetchall()]
    return matches, rows


def for_match(conn, match: dict, lambda_home: float, lambda_away: float) -> dict:
    """match: matches satırı (kickoff, home_id, away_id). Maçtan önceki verilerle iki takımın oyuncu gol olasılıkları."""
    out = {}
    for side, team_id, lam in (("home", match["home_id"], lambda_home), ("away", match["away_id"], lambda_away)):
        matches, rows = _team_data(conn, str(team_id), match["kickoff"]) if team_id else ([], [])
        out[side] = estimate(matches, rows, lam)
    out["note"] = ("Oyuncu olasılıkları geçmiş maçlardaki gol/dakika verisinden ve takımın beklenen golünden "
                   "türetilir; kadro ve sakatlık bilgisi yoktur. İddaa oyuncu oranı olmadığından değer hesaplanmaz.")
    return out
