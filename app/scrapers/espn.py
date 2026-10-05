"""ESPN'in herkese açık fikstür sayfalarından maç sonuçlarını ve fikstürü çeker.

API anahtarı kullanılmaz: sayfa HTML'inin içine gömülü JSON (window['__espnfitt__'])
okunur. Her istek, verilen tarihin çevresindeki ~1 haftalık pencereyi döndürür.
"""
import gzip
import json
import re
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone

from ..config import FIXTURE_DAYS_AHEAD, HISTORY_START, REQUEST_DELAY_SEC, USER_AGENT
from ..db import get_meta, set_meta

URL = "https://www.espn.com/soccer/fixtures/_/date/{day}/league/{league}"
_EMBED = re.compile(r"window\['__espnfitt__'\]=(\{.*?\});</script>", re.S)


def fetch_html(url: str, timeout: int = 25, retries: int = 3) -> str:
    # gzip ile sayfa ~540 KB yerine ~75 KB iner
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
    for attempt in range(retries):
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            body = raw.decode("utf-8", errors="ignore")
        if resp.status == 200 and body:
            return body
        time.sleep(2 * (attempt + 1))  # 202/boş gövde: kısa bekleyip tekrar dene
    raise RuntimeError(f"Boş yanıt: {url}")


def fetch_window(league: str, day: date) -> dict[str, list[dict]]:
    html = fetch_html(URL.format(day=day.strftime("%Y%m%d"), league=league))
    m = _EMBED.search(html)
    if not m:
        raise RuntimeError(f"ESPN sayfa yapısı değişmiş olabilir: {league} {day}")
    data = json.loads(m.group(1))
    return data.get("page", {}).get("content", {}).get("events", {}) or {}


def parse_event(ev: dict, league: str) -> dict | None:
    comps = ev.get("competitors") or []
    home = next((c for c in comps if c.get("isHome")), None)
    away = next((c for c in comps if not c.get("isHome")), None)
    if not home or not away:
        return None
    status = ev.get("status") or {}
    detail = status.get("detail") or ""
    completed = bool(ev.get("completed")) and status.get("state") == "post" and detail in ("FT", "AET", "FT-Pens")
    return {
        "id": str(ev["id"]),
        "league": league,
        "kickoff": ev.get("date"),
        "home": home.get("displayName"),
        "away": away.get("displayName"),
        "home_id": str(home.get("id")),
        "away_id": str(away.get("id")),
        "home_goals": home.get("score") if completed else None,
        "away_goals": away.get("score") if completed else None,
        "completed": 1 if completed else 0,
        "status": detail or status.get("state"),
    }


def upsert(conn, m: dict):
    conn.execute(
        """INSERT INTO matches(id, league, kickoff, home, away, home_id, away_id,
               home_goals, away_goals, completed, status, updated_at)
           VALUES(:id, :league, :kickoff, :home, :away, :home_id, :away_id,
               :home_goals, :away_goals, :completed, :status, :now)
           ON CONFLICT(id) DO UPDATE SET kickoff=excluded.kickoff, home=excluded.home,
               away=excluded.away, home_goals=excluded.home_goals, away_goals=excluded.away_goals,
               completed=excluded.completed, status=excluded.status, updated_at=excluded.updated_at""",
        {**m, "now": datetime.now(timezone.utc).isoformat()},
    )


def sync_league(conn, league: str, progress=None) -> int:
    """Ligi kaldığı yerden günceller. Dönen değer: işlenen maç sayısı."""
    today = date.today()
    end = today + timedelta(days=FIXTURE_DAYS_AHEAD)
    done = get_meta(conn, f"espn_done_{league}")
    day = max(HISTORY_START, date.fromisoformat(done)) if done else HISTORY_START
    count = 0
    while day <= end:
        if progress:
            progress(f"{league}: {day.isoformat()} haftası çekiliyor")
        try:
            window = fetch_window(league, day)
        except Exception as exc:  # ağ hatası: bir sonraki pencereye geç
            if progress:
                progress(f"{league}: {day} alınamadı ({exc})")
            day += timedelta(days=3)
            time.sleep(REQUEST_DELAY_SEC)
            continue
        for events in window.values():
            for ev in events:
                parsed = parse_event(ev, league)
                if parsed:
                    upsert(conn, parsed)
                    count += 1
        days = sorted(date(int(k[:4]), int(k[4:6]), int(k[6:])) for k in window.keys())
        if days and days[-1] > day:
            day = days[-1]  # son gün eksik gelmiş olabilir, oradan devam et
        else:
            day += timedelta(days=1 if any(window.values()) else 3)
        # kaldığı yeri kaydet (yarıda kesilirse baştan başlamasın); son 5 gün hep yeniden kontrol edilir
        set_meta(conn, f"espn_done_{league}", min(day, today - timedelta(days=5)).isoformat())
        conn.commit()
        time.sleep(REQUEST_DELAY_SEC)
    # Son 5 günü her seferinde yeniden kontrol et (ertelenen/yeni biten maçlar)
    set_meta(conn, f"espn_done_{league}", (today - timedelta(days=5)).isoformat())
    return count
