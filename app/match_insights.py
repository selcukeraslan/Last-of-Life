"""Maç detayı için ek içgörüler: form, H2H, gol istatistikleri, 7 günlük haberler, oran serisi."""
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from . import odds_history, ops
from .config import LEAGUES
from .db import session

router = APIRouter(prefix="/api/match", tags=["match-insights"])
NEWS_DAYS = 7


def _recent(conn, team: str, league: str, before: str, n: int = 5) -> list[dict]:
    rows = conn.execute(
        """SELECT kickoff, home, away, home_goals, away_goals FROM matches
           WHERE league=? AND completed=1 AND home_goals IS NOT NULL AND kickoff < ?
             AND (home=? OR away=?) ORDER BY kickoff DESC LIMIT ?""", (league, before, team, team, n)).fetchall()
    out = []
    for r in rows:
        is_home = r["home"] == team
        gf, ga = (r["home_goals"], r["away_goals"]) if is_home else (r["away_goals"], r["home_goals"])
        out.append({"date": r["kickoff"][:10], "opp": r["away"] if is_home else r["home"], "venue": "E" if is_home else "D",
                    "gf": gf, "ga": ga, "res": "G" if gf > ga else "B" if gf == ga else "M"})
    return out


def _goal_stats(conn, team: str, league: str, before: str) -> dict | None:
    rows = conn.execute(
        """SELECT home, home_goals, away_goals FROM matches
           WHERE league=? AND completed=1 AND home_goals IS NOT NULL AND kickoff < ? AND (home=? OR away=?)""",
        (league, before, team, team)).fetchall()
    if not rows:
        return None
    games = []
    for r in rows:
        h = r["home"] == team
        games.append((h, r["home_goals"] if h else r["away_goals"], r["away_goals"] if h else r["home_goals"]))

    def avg(sel, i):
        return round(sum(g[i] for g in sel) / len(sel), 2) if sel else None
    ev, dep = [g for g in games if g[0]], [g for g in games if not g[0]]
    n = len(games)
    pct = lambda f: round(100 * sum(1 for g in games if f(g)) / n)
    return {"n": n, "for_home": avg(ev, 1), "against_home": avg(ev, 2), "for_away": avg(dep, 1), "against_away": avg(dep, 2),
            "btts": pct(lambda g: g[1] > 0 and g[2] > 0), "over25": pct(lambda g: g[1] + g[2] >= 3),
            "clean_sheet": pct(lambda g: g[2] == 0)}


def _safe_link(url):
    """Yalnız http(s) bağlantılar; aksi halde None (arayüzde düz metin)."""
    return url if isinstance(url, str) and urlparse(url.strip()).scheme in ("http", "https") else None


def _news(conn, team: str, league: str) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=NEWS_DAYS)).isoformat()
    rows = conn.execute(
        """SELECT title, link, source, published, injury FROM news
           WHERE league=? AND team=? AND published >= ? ORDER BY injury DESC, published DESC LIMIT 6""",
        (league, team, since)).fetchall()
    return [{"title": r["title"], "link": _safe_link(r["link"]), "source": r["source"], "published": r["published"],
             "injury": bool(r["injury"])} for r in rows]


def build(match_id: str) -> dict | None:
    with session() as conn:
        m = conn.execute("SELECT * FROM matches WHERE id=?", (str(match_id),)).fetchone()
        if not m or m["league"] not in LEAGUES:
            return None
        lg, k = m["league"], m["kickoff"]
        h2h = conn.execute(
            """SELECT kickoff, home, away, home_goals, away_goals FROM matches
               WHERE league=? AND completed=1 AND home_goals IS NOT NULL AND kickoff < ?
                 AND ((home=? AND away=?) OR (home=? AND away=?)) ORDER BY kickoff DESC LIMIT 5""",
            (lg, k, m["home"], m["away"], m["away"], m["home"])).fetchall()
        hist = odds_history.history_for_match(conn, match_id)
        return {
            "form": {"home": _recent(conn, m["home"], lg, k), "away": _recent(conn, m["away"], lg, k)},
            "h2h": [{"date": r["kickoff"][:10], "home": r["home"], "away": r["away"],
                     "score": f"{r['home_goals']}-{r['away_goals']}"} for r in h2h],
            "goals": {"home": _goal_stats(conn, m["home"], lg, k), "away": _goal_stats(conn, m["away"], lg, k)},
            "news": {"home": _news(conn, m["home"], lg), "away": _news(conn, m["away"], lg)},
            "odds": (hist or {}).get("markets", {}),
        }


@router.get("/{match_id}/insights")
def insights(match_id: str):
    def load():
        data = build(match_id)
        if data is None:  # istisna önbelleğe girmez
            raise HTTPException(404, "Maç bulunamadı")
        return data
    return ops.cached(("match-insights", match_id), load)
