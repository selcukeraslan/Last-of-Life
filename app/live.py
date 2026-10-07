"""Short lived ESPN live scoreboard cache for serverless requests."""
import time
import urllib.request
from datetime import datetime, timezone

from .config import LEAGUES, USER_AGENT

_CACHE_SECONDS = 45
_cache = {"at": 0.0, "matches": []}


def _parse_event(event, league):
    competitors = event.get("competitions", [{}])[0].get("competitors", [])
    home = next((x for x in competitors if x.get("homeAway") == "home"), None)
    away = next((x for x in competitors if x.get("homeAway") == "away"), None)
    if not home or not away:
        return None
    status = event.get("status", {})
    typ = status.get("type", {})
    state = typ.get("state")
    if state not in ("in", "post"):
        return None
    clock = status.get("displayClock") or typ.get("detail") or ""
    period = status.get("period")
    minute = f"{clock}'" if clock and state == "in" else (typ.get("shortDetail") or "MS")
    return {
        "id": str(event.get("id")), "league": league,
        "home": home.get("team", {}).get("displayName", ""),
        "away": away.get("team", {}).get("displayName", ""),
        "home_goals": int(home.get("score") or 0), "away_goals": int(away.get("score") or 0),
        "minute": minute, "period": period, "state": state,
    }


def _fetch(league):
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=8) as response:
        import json
        return json.loads(response.read().decode("utf-8"))


def get_live_matches():
    now = time.monotonic()
    if now - _cache["at"] < _CACHE_SECONDS:
        return list(_cache["matches"])
    matches = []
    for league in LEAGUES:
        try:
            for event in _fetch(league).get("events", []):
                parsed = _parse_event(event, league)
                if parsed:
                    matches.append(parsed)
        except Exception:
            continue
    _cache.update(at=now, matches=matches)
    return list(matches)
