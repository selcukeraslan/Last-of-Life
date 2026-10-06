"""TFF resmi sitesinden (tff.org) lig fikstürü ve sonuçları.

ESPN, TFF 1. Lig için `tur.2` sluğunu listeliyor ama hiç maç/takım döndürmüyor; TheSportsDB'nin ücretsiz
anahtarı da her haftanın yarısını veriyor. Bu yüzden bu lig resmi siteden okunur: sayfa `hafta=N` ile haftalık
maçları (tarih, saat, takım, skor) verir. Çıktı ESPN toplayıcısıyla aynı `matches` biçimindedir.
Takım ve maç kimlikleri `tff-` önekiyle yazılır (ESPN logosu yoktur).
"""
import gzip
import html
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ..config import FIXTURE_DAYS_AHEAD, REQUEST_DELAY_SEC, USER_AGENT
from ..db import get_meta, set_meta
from .espn import upsert

URL = "https://www.tff.org/default.aspx?pageID={page}"
LEAGUE_PAGES = {"tur.2": 142}  # Trendyol 1. Lig fikstür ve puan cetveli
TZ = ZoneInfo("Europe/Istanbul")
MATCH_MINUTES = 150  # bu süre geçmeden gösterilen skor canlı sayılır (maç bitmiş değil)

# Sponsor adlı resmi unvanlar yerine kısa ad (kulüp kimliği -> ad). Adlar iddaa.com yazımıyla uyumludur.
CLUB_NAMES = {
    "9387": "Iğdır FK", "52": "Antalyaspor", "2020": "Vanspor FK", "130": "Bandırmaspor",
    "34": "Batman Petrolspor", "4824": "Bodrum FK", "3593": "Boluspor", "3601": "Bursaspor",
    "74": "Sivasspor", "3661": "Ümraniyespor", "6": "Ankara Keçiörengücü", "2861": "Manisa FK",
    "8758": "Mardin 1969 Spor", "72": "Kayserispor", "3611": "Fatih Karagümrük", "82": "Muğlaspor",
    "3623": "Pendikspor", "3602": "Sarıyer", "964": "Esenler Erokspor", "3617": "İstanbulspor",
}
_LEGAL = re.compile(r"\b(A\.?Ş\.?|FUTBOL|KULÜBÜ|KULUBU|KULÜP|A\.\.)\b\.?", re.I)

_ROW = re.compile(r'<tr class="haftaninMaclariTr">(.*?)</tr>', re.S)
_DATE = re.compile(r'lblTarih">(\d\d)\.(\d\d)\.(\d{4})<')
_TIME = re.compile(r'lblSaat">(\d\d):(\d\d)<')
_CLUB = re.compile(r'kulupID=(\d+)"[^>]*>\s*<span[^>]*>([^<]*)</span>', re.S | re.I)
_SCORE = re.compile(r'Label5">\s*(\d*)\s*</span>.*?Label6">\s*(\d*)\s*</span>', re.S)
_MAC = re.compile(r"macId=(\d+)")
_WEEK_TAB = re.compile(r">\s*(\d+)\s*\.\s*Hafta\s*<")
_WEEK_SELECTED = re.compile(r'aspNetDisabled[^>]*>\s*<span class="wrap">\s*<span class="innerWrap">\s*(\d+)\s*\.\s*Hafta')


def club_name(club_id: str, raw: str) -> str:
    if club_id in CLUB_NAMES:
        return CLUB_NAMES[club_id]
    cleaned = " ".join(_LEGAL.sub(" ", html.unescape(raw)).split())
    return " ".join(w[:1] + w[1:].replace("İ", "i").replace("I", "ı").lower() for w in (cleaned or raw).split()).replace("İ", "i")


def fetch_page(page: int, week: int | None = None, timeout: int = 25, retries: int = 3) -> str:
    url = URL.format(page=page) + (f"&hafta={week}" if week else "")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
            body = raw.decode("cp1254", errors="replace")  # TFF sayfaları windows-1254
            if "haftaninMaclariTr" in body:
                return body
            last = RuntimeError("TFF sayfa yapısı değişmiş olabilir")
        except Exception as exc:
            last = exc
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"TFF sayfası alınamadı: {url} ({last})")


def parse_page(body: str, league: str, now: datetime | None = None) -> dict:
    """Bir hafta sayfasından {"week", "total_weeks", "matches"} çıkarır."""
    now = now or datetime.now(timezone.utc)
    matches = []
    selected = _WEEK_SELECTED.search(body)
    week = int(selected.group(1)) if selected else None
    for row in _ROW.findall(body):
        d, t, clubs, mac = _DATE.search(row), _TIME.search(row), _CLUB.findall(row), _MAC.search(row)
        if not (d and t and len(clubs) >= 2 and mac):
            continue  # tarihi/saati henüz belli olmayan maç
        local = datetime(int(d.group(3)), int(d.group(2)), int(d.group(1)),
                         int(t.group(1)), int(t.group(2)), tzinfo=TZ)
        kickoff = local.astimezone(timezone.utc)
        score = _SCORE.search(row)
        hg = ag = None
        if score and score.group(1) != "" and score.group(2) != "":
            hg, ag = int(score.group(1)), int(score.group(2))
        # Canlı maçta skor görünür; bitmiş saymak için maç süresi geçmiş olmalı.
        completed = hg is not None and now >= kickoff + timedelta(minutes=MATCH_MINUTES)
        (hid, hraw), (aid, araw) = clubs[0], clubs[1]
        matches.append({
            "id": f"tff-{mac.group(1)}", "league": league,
            "kickoff": kickoff.strftime("%Y-%m-%dT%H:%MZ"),
            "home": club_name(hid, hraw), "away": club_name(aid, araw),
            "home_id": f"tff-{hid}", "away_id": f"tff-{aid}",
            "home_goals": hg if completed else None, "away_goals": ag if completed else None,
            "completed": 1 if completed else 0,
            "status": "FT" if completed else (f"{week}. Hafta" if week else None),
        })
    weeks = [int(w) for w in _WEEK_TAB.findall(body)]
    return {"week": week, "total_weeks": max(weeks) if weeks else None, "matches": matches}


def fetch_week(league: str, week: int | None = None, **kw) -> dict:
    return parse_page(fetch_page(LEAGUE_PAGES[league], week, **kw), league)


def _store(conn, result: dict) -> int:
    for m in result["matches"]:
        upsert(conn, m)
    conn.commit()
    return len(result["matches"])


def sync_league(conn, league: str, progress=None) -> int:
    """Sezonun oynanmış haftalarını ve yakın haftaları çeker; tamamlanan haftalar bir sonraki sefer atlanır."""
    first = fetch_week(league)
    current, total = first["week"] or 1, first["total_weeks"] or 38
    last = min(total, current + -(-FIXTURE_DAYS_AHEAD // 7))
    key = f"tff_done_{league}"
    start = min(int(get_meta(conn, key, "1") or 1), current)
    count, contiguous = 0, True
    for week in range(start, last + 1):
        if progress:
            progress(f"{league}: {week}. hafta çekiliyor")
        result = first if week == current else fetch_week(league, week)
        if result["week"] not in (None, week):
            continue  # sayfa istenen haftayı göstermedi; yanlış haftayı yazma
        count += _store(conn, result)
        if contiguous and result["matches"] and all(m["completed"] for m in result["matches"]):
            set_meta(conn, key, str(week + 1))
        else:
            contiguous = False
        conn.commit()
        if week != current:
            time.sleep(REQUEST_DELAY_SEC)
    return count


def sync_recent(conn, league: str, days_back: int = 3, max_requests: int = 2, progress=None) -> tuple[int, bool]:
    """Hızlı güncelleme: bu hafta + önceki hafta (en çok `max_requests` istek, kısa zaman aşımı)."""
    count, ok = 0, False
    try:
        current = fetch_week(league, timeout=12, retries=2)
    except Exception as exc:
        if progress:
            progress(f"{league}: alınamadı ({exc})")
        return 0, False
    ok = True
    count += _store(conn, current)
    week = current["week"]
    if max_requests > 1 and week and week > 1:
        try:
            count += _store(conn, fetch_week(league, week - 1, timeout=12, retries=2))
        except Exception as exc:
            if progress:
                progress(f"{league}: {week - 1}. hafta alınamadı ({exc})")
    return count, ok
