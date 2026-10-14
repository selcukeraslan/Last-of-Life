"""ESPN maç özetlerinden (herkese açık site API'si, anahtarsız) oyuncu bazlı maç istatistikleri.

Özet JSON'u `rosters` altında her oyuncu için kadro bilgisi (ilk 11 / yedek, oyundan çıkma-girme
dakikası) ve `totalGoals`, `totalShots`, `shotsOnTarget` istatistiklerini verir. Oyuncu gol oranları
bu veriden `model/players.py` ile hesaplanır. Yalnız ESPN kaynaklı ligler (TFF ligleri hariç) çekilir;
özeti çekilmiş maç `player_fetch_log`'a yazılır, böylece her maç bir kez çekilir.
"""
import json
import re
import time
from datetime import datetime, timezone

from ..config import LEAGUES, REQUEST_DELAY_SEC
from .espn import fetch_html

SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/summary?event={event}"

SCHEMA = """
CREATE TABLE IF NOT EXISTS player_match_stats (
    match_id TEXT NOT NULL,
    player_id TEXT NOT NULL,
    team_id TEXT NOT NULL,
    name TEXT NOT NULL,
    position TEXT,
    starter INTEGER NOT NULL DEFAULT 0,
    minutes REAL NOT NULL DEFAULT 0,
    goals INTEGER NOT NULL DEFAULT 0,
    shots INTEGER NOT NULL DEFAULT 0,
    shots_on_target INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (match_id, player_id)
);
CREATE INDEX IF NOT EXISTS ix_player_stats_team ON player_match_stats(team_id, match_id);
CREATE TABLE IF NOT EXISTS player_fetch_log (
    match_id TEXT PRIMARY KEY,
    fetched_at TEXT NOT NULL,
    players INTEGER NOT NULL DEFAULT 0
);
"""

_MINUTE = re.compile(r"(\d+)")


def _minute(display) -> int | None:
    m = _MINUTE.match(str(display or "").strip())
    return int(m.group(1)) if m else None


def _stat(entry: dict, name: str) -> int:
    for s in entry.get("stats") or []:
        if s.get("name") == name:
            try:
                return int(s.get("value") or 0)
            except (TypeError, ValueError):
                return 0
    return 0


def _sub_minute(entry: dict) -> int | None:
    for play in entry.get("plays") or []:
        if play.get("substitution"):
            return _minute((play.get("clock") or {}).get("displayValue"))
    return None


def _minutes(entry: dict) -> float:
    """Oynadığı dakika: ilk 11 -> 90 veya oyundan çıkış dakikası, yedek -> 90 - giriş dakikası."""
    sub = _sub_minute(entry)
    if entry.get("starter"):
        return float(min(90, sub if entry.get("subbedOut") and sub else 60 if entry.get("subbedOut") else 90))
    if entry.get("subbedIn"):
        return float(max(1, 90 - sub) if sub else 20)
    return 0.0


def parse_summary(data: dict) -> list[dict]:
    """Özet JSON'undan oynayan oyuncu satırları (yedekte kalıp girmeyenler atlanır)."""
    rows = []
    for side in data.get("rosters") or []:
        team_id = str((side.get("team") or {}).get("id") or "")
        for entry in side.get("roster") or []:
            athlete = entry.get("athlete") or {}
            minutes = _minutes(entry)
            if not team_id or not athlete.get("id") or minutes <= 0:
                continue
            rows.append({"player_id": str(athlete["id"]), "team_id": team_id,
                         "name": athlete.get("displayName") or athlete.get("fullName") or "?",
                         "position": (entry.get("position") or {}).get("abbreviation"),
                         "starter": int(bool(entry.get("starter"))), "minutes": minutes,
                         "goals": _stat(entry, "totalGoals"), "shots": _stat(entry, "totalShots"),
                         "shots_on_target": _stat(entry, "shotsOnTarget")})
    return rows


def fetch_summary(league: str, event_id: str) -> dict:
    return json.loads(fetch_html(SUMMARY_URL.format(league=league, event=event_id)))


def store(conn, match_id: str, rows: list[dict], now: str):
    conn.execute("DELETE FROM player_match_stats WHERE match_id=?", (match_id,))
    for r in rows:
        conn.execute(
            "INSERT INTO player_match_stats(match_id, player_id, team_id, name, position, starter, minutes, goals, "
            "shots, shots_on_target) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (match_id, r["player_id"], r["team_id"], r["name"], r["position"], r["starter"], r["minutes"],
             r["goals"], r["shots"], r["shots_on_target"]))
    conn.execute("INSERT INTO player_fetch_log(match_id, fetched_at, players) VALUES(?,?,?) "
                 "ON CONFLICT(match_id) DO UPDATE SET fetched_at=excluded.fetched_at, players=excluded.players",
                 (match_id, now, len(rows)))


def pending_matches(conn, limit: int) -> list[dict]:
    """Özeti henüz çekilmemiş, bitmiş ESPN maçları (en yeniden eskiye)."""
    espn_leagues = [lg for lg, cfg in LEAGUES.items() if cfg.get("source") != "tff"]
    marks = ",".join("?" for _ in espn_leagues)
    rows = conn.execute(
        f"SELECT m.id, m.league FROM matches m LEFT JOIN player_fetch_log l ON l.match_id=m.id "
        f"WHERE m.completed=1 AND l.match_id IS NULL AND m.league IN ({marks}) "
        f"ORDER BY m.kickoff DESC LIMIT ?", (*espn_leagues, limit)).fetchall()
    return [dict(r) for r in rows]


def sync_players(conn, limit: int = 40, deadline: float | None = None, progress=None) -> int:
    """En yeni `limit` maçın oyuncu istatistiklerini çeker; `deadline` (monotonic) aşılırsa durur.
    Bir maçın hatası diğerlerini durdurmaz. Çekilen maç sayısını döndürür."""
    done = 0
    for m in pending_matches(conn, limit):
        if deadline is not None and time.monotonic() > deadline:
            break
        try:
            rows = parse_summary(fetch_summary(m["league"], m["id"]))
        except Exception as exc:
            if progress:
                progress(f"Oyuncu özeti alınamadı ({m['id']}): {exc}")
            continue
        store(conn, m["id"], rows, datetime.now(timezone.utc).isoformat(timespec="seconds"))
        conn.commit()
        done += 1
        time.sleep(REQUEST_DELAY_SEC)
    return done


if __name__ == "__main__":
    import sys
    from ..db import init_db, session
    init_db()
    n = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 100
    with session() as c:
        print(f"{sync_players(c, n, progress=print)} maç işlendi")
