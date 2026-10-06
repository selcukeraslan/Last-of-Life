"""iddaa.com'un herkese açık maç öncesi bülteninden oranları çeker.

Site bu uç noktayı kendi program sayfasında XHR ile kullanıyor; API anahtarı veya
oturum gerektirmiyor. Alan adları kısa tutulduğu için market sözleşmesi burada
tek yerde çevrilir. Site sözleşmesi değişirse uygulamanın geri kalanı etkilenmez.
"""
import gzip
import json
import re
import time
import unicodedata
import urllib.request
from datetime import datetime, timezone
from difflib import SequenceMatcher

from ..config import USER_AGENT
from .. import odds_history
from ..db import set_meta

EVENTS_URL = "https://sportsbookv2.iddaa.com/sportsbook/events?st=1&type=0&version=0"

# iddaa competition id -> ESPN lig anahtarı. Kimlikler /sportsbook/competitions
# yanıtındaki kalıcı futbol organizasyonu kimlikleridir.
COMPETITION_IDS = {
    584: "tur.1",   # Türkiye Süper Lig
    43: "eng.1",    # İngiltere Premier Lig
    129: "esp.1",   # İspanya La Liga
    143: "ita.1",   # İtalya Serie A
    45: "ger.1",    # Almanya Bundesliga
    381: "fra.1",   # Fransa Ligue 1
}

_CHAR_MAP = str.maketrans({"ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g"})
_NON_WORD = re.compile(r"[^a-z0-9]+")

# Kaynaklar arasında düzenli görülen kısa/ad değişiklikleri. Değerler yalnızca
# eşleştirme anahtarıdır; arayüzde takım adını değiştirmez.
_ALIAS_GROUPS = {
    "manchester city": ["man city"],
    "manchester united": ["man utd"],
    "nottingham forest": ["nottm forest"],
    "wolverhampton": ["wolverhampton wanderers", "wolves"],
    "tottenham": ["tottenham hotspur", "spurs"],
    "newcastle": ["newcastle united"],
    "west ham": ["west ham united"],
    "brighton": ["brighton hove albion", "brighton and hove albion"],
    "psg": ["paris saint germain", "paris sg"],
    "marseille": ["olympique marseille", "olympique de marseille"],
    "lyon": ["olympique lyon", "olympique lyonnais"],
    "inter": ["inter milan", "internazionale"],
    "ac milan": ["milan"],
    "hellas verona": ["verona"],
    "atletico madrid": ["atletico de madrid"],
    "athletic bilbao": ["athletic club"],
    "celta vigo": ["celta de vigo"],
    "bayern munich": ["bayern munchen", "bayern munih", "fc bayern munchen"],
    "borussia monchengladbach": ["bor monchengladbach", "gladbach"],
    "mainz": ["mainz 05", "1 fsv mainz 05"],
    "rb leipzig": ["rasenballsport leipzig"],
    "basaksehir": ["istanbul basaksehir", "rams basaksehir"],
    "gaziantep": ["gaziantep fk", "gazisehir gaziantep"],
    "rizespor": ["caykur rizespor"],
    "goztepe": ["goztepe sk"],
    "kasimpasa": ["kasimpasa sk"],
    "eyupspor": ["ikas eyupspor"],
    "fenerbahce": ["fenerbahce sk"],
    "galatasaray": ["galatasaray sk"],
    "besiktas": ["besiktas jk"],
    "trabzonspor": ["trabzonspor sk"],
}


def _basic_name(value: str) -> str:
    value = (value or "").translate(_CHAR_MAP).casefold()
    value = "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))
    value = _NON_WORD.sub(" ", value).strip()
    tokens = [t for t in value.split() if t not in {"fc", "cf", "fk", "sk", "as", "ssc", "afc"}]
    return " ".join(tokens)


TEAM_ALIASES = {}
for _canonical, _variants in _ALIAS_GROUPS.items():
    for _name in [_canonical, *_variants]:
        TEAM_ALIASES[_basic_name(_name)] = _canonical


def normalize_team(value: str) -> str:
    normalized = _basic_name(value)
    return TEAM_ALIASES.get(normalized, normalized)


def team_similarity(a: str, b: str) -> float:
    a, b = normalize_team(a), normalize_team(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ta, tb = set(a.split()), set(b.split())
    token_score = 2 * len(ta & tb) / (len(ta) + len(tb))
    return max(token_score, SequenceMatcher(None, a, b).ratio())


def fetch_json(url: str = EVENTS_URL, timeout: int = 25, retries: int = 3) -> dict:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "Origin": "https://www.iddaa.com",
        "Referer": "https://www.iddaa.com/program/futbol",
    }
    req = urllib.request.Request(url, headers=headers)
    last_error = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                data = json.loads(raw.decode("utf-8"))
            if not data.get("isSuccess"):
                raise RuntimeError(data.get("message") or "iddaa başarısız yanıt verdi")
            return data
        except Exception as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"iddaa bülteni alınamadı: {last_error}")


def _market_odds(markets: list[dict]) -> dict[str, float]:
    odds: dict[str, float] = {}
    for market in markets or []:
        if market.get("s") != 1:
            continue
        key = (market.get("t"), market.get("st"))
        outcomes = market.get("o") or []
        mapped: dict[int, str] = {}
        if key == (1, 1):
            mapped = {1: "1", 2: "X", 3: "2"}
        elif key == (2, 92):
            mapped = {1: "1X", 2: "12", 3: "X2"}
        elif key == (2, 89):
            mapped = {1: "KG Var", 2: "KG Yok"}
        elif key == (2, 101) and str(market.get("sov")) in {"1.5", "2.5", "3.5"}:
            line = str(market["sov"])
            mapped = {1: f"A{line}", 2: f"Ü{line}"}
        if not mapped:
            continue
        for outcome in outcomes:
            market_name = mapped.get(outcome.get("no"))
            odd = outcome.get("odd")
            if market_name and isinstance(odd, (int, float)) and odd > 1:
                odds[market_name] = round(float(odd), 2)
    return odds


def parse_event(raw: dict) -> dict | None:
    league = COMPETITION_IDS.get(raw.get("ci"))
    if not league or not raw.get("d"):
        return None
    return {
        "id": str(raw["i"]),
        "league": league,
        "competition_id": raw["ci"],
        "kickoff": datetime.fromtimestamp(raw["d"], timezone.utc).isoformat(),
        "home": raw.get("hn") or "",
        "away": raw.get("an") or "",
        "odds": _market_odds(raw.get("m") or []),
    }


def match_event(event: dict, fixtures: list[dict]) -> tuple[dict | None, float]:
    kickoff = datetime.fromisoformat(event["kickoff"])
    best, best_score = None, 0.0
    for fixture in fixtures:
        if fixture["league"] != event["league"]:
            continue
        fixture_time = datetime.fromisoformat(fixture["kickoff"].replace("Z", "+00:00"))
        hours = abs((fixture_time - kickoff).total_seconds()) / 3600
        if hours > 18:
            continue
        home_score = team_similarity(event["home"], fixture["home"])
        away_score = team_similarity(event["away"], fixture["away"])
        if min(home_score, away_score) < 0.58 or (home_score + away_score) / 2 < 0.72:
            continue
        score = 0.45 * home_score + 0.45 * away_score + 0.10 * (1 - hours / 18)
        if score > best_score:
            best, best_score = fixture, score
    return best, round(best_score, 3)


def sync_odds(conn, progress=None, retries: int = 3) -> dict:
    payload = fetch_json(retries=retries)
    raw_events = payload["data"].get("events", [])
    events = [parsed for raw in raw_events if (parsed := parse_event(raw))]
    fixtures = [dict(row) for row in conn.execute(
        "SELECT id, league, kickoff, home, away FROM matches WHERE completed=0"
    ).fetchall()]
    now = datetime.now(timezone.utc).isoformat()

    # Yalnız başarılı ve parse edilebilir bir yanıttan sonra eski bülteni değiştir.
    conn.execute("DELETE FROM iddaa_odds")
    conn.execute("DELETE FROM iddaa_events")
    # Bir ESPN maçına en fazla bir iddaa etkinliği bağlanır; aksi halde iki etkinliğin
    # (ör. aynı maçın özel/kopya kaydı) oranları tek maçta karışırdı.
    best_for_fixture: dict[str, tuple[float, str]] = {}
    pairs = []
    for event in events:
        fixture, score = match_event(event, fixtures)
        pairs.append((event, fixture, score))
        if fixture and score > best_for_fixture.get(fixture["id"], (0.0, ""))[0]:
            best_for_fixture[fixture["id"]] = (score, event["id"])
    matched = odds_count = 0
    for event, fixture, score in pairs:
        if fixture and best_for_fixture[fixture["id"]][1] != event["id"]:
            fixture, score = None, 0.0
        match_id = fixture["id"] if fixture else None
        matched += int(fixture is not None)
        conn.execute(
            """INSERT INTO iddaa_events
               (id, league, competition_id, kickoff, home, away, match_id, match_score, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event["id"], event["league"], event["competition_id"], event["kickoff"],
             event["home"], event["away"], match_id, score or None, now),
        )
        for market, odd in event["odds"].items():
            conn.execute("INSERT INTO iddaa_odds(event_id, market, odd) VALUES (?, ?, ?)",
                         (event["id"], market, odd))
            odds_count += 1

    odds_history.record_snapshot(conn, events, now)
    odds_history.prune(conn)

    stats = {"bulletin_events": len(raw_events), "supported_events": len(events),
             "matched": matched, "odds": odds_count,
             "rate": round(matched / len(events), 3) if events else None}
    set_meta(conn, "iddaa_last_update", now)
    set_meta(conn, "iddaa_last_error", "")
    set_meta(conn, "iddaa_stats", json.dumps(stats, ensure_ascii=False))
    if progress:
        pct = f"%{stats['rate'] * 100:.0f}" if stats["rate"] is not None else "-"
        progress(f"iddaa.com: bültende {len(raw_events)} futbol maçı; desteklenen liglerde "
                 f"{len(events)} maç, {matched} eşleşme ({pct}), {odds_count} oran")
    return stats


def odds_for_matches(conn, match_ids) -> dict[str, dict]:
    """ESPN maç kimliği -> {"event_id", "updated_at", "odds": {pazar: oran}} (yalnız eşleşenler)."""
    match_ids = [str(m) for m in match_ids]
    if not match_ids:
        return {}
    marks = ",".join("?" for _ in match_ids)
    rows = conn.execute(
        f"""SELECT e.match_id, e.id event_id, e.updated_at, o.market, o.odd
            FROM iddaa_events e JOIN iddaa_odds o ON o.event_id=e.id
            WHERE e.match_id IN ({marks})""", match_ids).fetchall()
    out: dict[str, dict] = {}
    for row in rows:
        entry = out.setdefault(row["match_id"], {
            "event_id": row["event_id"], "updated_at": row["updated_at"], "odds": {}})
        entry["odds"][row["market"]] = row["odd"]
    return out
