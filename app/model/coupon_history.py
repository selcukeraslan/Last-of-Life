"""Kupon geçmişi: günün Banko / Sürpriz kuponunu dondurur, sonuçlara göre işaretler, kâr/zararı hesaplar.

* freeze(): kupon (gün, tür) başına bir kez, ilk üretildiği haliyle `saved_coupons` / `saved_coupon_picks`
  tablolarına yazılır; sonradan oranlar veya tahminler değişse de kayıt değişmez. Seçimi olmayan (boş)
  kupon kaydedilmez; gün içinde uygun kupon çıkarsa sonraki çalışmada kaydedilir.
* settle(): biten maçlara göre her seçimi won / lost / void, kuponu da won / lost / pending / void yapar.
  Tek seçim yattıysa kupon hemen yatmıştır; ertelenen / iptal edilen maç oranı 1.00 sayılır (void).
* history(): tutma oranı, "her gün KUPON_BASINA 100 TL" kâr/zarar + ROI ve günlük liste.
"""
import re
from datetime import datetime, timedelta, timezone

from .coupons import TZ, build_coupons

STAKE = 100.0  # simülasyon: her gün, her kupona yatırılan TL
KINDS = ("banko", "surprise")
VOID_AFTER_DAYS = 7  # bu kadar gün geçtiği halde bitmeyen maç iptal sayılır
_VOID_STATUS = ("postpon", "cancel", "abandon", "suspend")  # ESPN durum metni (küçük harf)
_TOTALS = re.compile(r"^([ÜA])(\d\.\d)$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def pick_result(market: str, home_goals: int, away_goals: int) -> str | None:
    """Skora göre 'won' / 'lost'; tanınmayan pazar için None (seçim bekliyor kalır)."""
    h, a = home_goals, away_goals
    rules = {"1": h > a, "X": h == a, "2": h < a, "1X": h >= a, "12": h != a, "X2": h <= a,
             "KG Var": h > 0 and a > 0, "KG Yok": h == 0 or a == 0, "Ev 0.5Ü": h >= 1, "Dep 0.5Ü": a >= 1}
    if market in rules:
        won = rules[market]
    elif m := _TOTALS.match(market):
        total, line = h + a, float(m.group(2))
        won = total > line if m.group(1) == "Ü" else total < line
    else:
        return None
    return "won" if won else "lost"


def coupon_status(pick_statuses: list[str]) -> str:
    if "lost" in pick_statuses:
        return "lost"
    if "pending" in pick_statuses:
        return "pending"
    return "void" if all(s == "void" for s in pick_statuses) else "won"


# --- Dondurma ----------------------------------------------------------------------
def freeze(conn, coupons: dict) -> list[str]:
    """`build_coupons` çıktısındaki boş olmayan kuponları, daha önce kaydedilmemişse yazar.
    Yarışta (iki istek aynı anda) birincil anahtar tek kaydı garanti eder. Yeni kaydedilen türleri döner."""
    saved, now = [], _now().isoformat(timespec="seconds")
    for kind in KINDS:
        c = coupons.get(kind) or {}
        picks = c.get("picks") or []
        if not picks:
            continue
        cur = conn.execute(
            "INSERT INTO saved_coupons(day, kind, total_odds, total_probability, odds_source, status, created_at) "
            "VALUES(?, ?, ?, ?, ?, 'pending', ?) ON CONFLICT(day, kind) DO NOTHING",
            (coupons["date"], kind, c["total_odds"], c["total_probability"], c.get("odds_source"), now))
        if cur.rowcount != 1:
            continue
        for p in picks:
            conn.execute(
                "INSERT INTO saved_coupon_picks(day, kind, match_id, league, league_name, kickoff, home, away, "
                "market, odds, odds_source, probability, status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'pending')",
                (coupons["date"], kind, str(p["id"]), p["league"], p.get("league_name"), p["kickoff"], p["home"],
                 p["away"], p["market"], p["odds"], p.get("odds_source"), p["p"]))
        saved.append(kind)
    return saved


def freeze_today() -> list[str]:
    """Bugünün (Türkiye saati) kuponlarını üretip dondurur (güncelleme akışından çağrılır)."""
    from ..db import session
    coupons = build_coupons(datetime.now(TZ).date())
    with session() as conn:
        return freeze(conn, coupons)


def freeze_if_today(coupons: dict) -> list[str]:
    """/api/coupons yanıtı bugüne aitse dondurur. Kayıt hatası kupon yanıtını asla bozmaz."""
    if coupons.get("date") != datetime.now(TZ).date().isoformat():
        return []
    try:
        from ..db import session
        with session() as conn:
            return freeze(conn, coupons)
    except Exception as exc:
        print(f"Kupon geçmişi kaydedilemedi: {exc}", flush=True)
        return []


# --- Sonuçlandırma -------------------------------------------------------------------
def _pick_outcome(row) -> tuple[str, int | None, int | None]:
    """Bekleyen bir seçimin (durum, ev golü, dep golü) bilgisi; maç bitmediyse ('pending', None, None)."""
    if row["completed"] and row["home_goals"] is not None and row["away_goals"] is not None:
        res = pick_result(row["market"], row["home_goals"], row["away_goals"])
        return (res or "pending"), row["home_goals"], row["away_goals"]
    status = (row["match_status"] or "").lower()
    kickoff = datetime.fromisoformat(row["kickoff"].replace("Z", "+00:00"))
    if any(w in status for w in _VOID_STATUS) and _now() > kickoff + timedelta(days=1):
        return "void", None, None
    if _now() > kickoff + timedelta(days=VOID_AFTER_DAYS):
        return "void", None, None
    return "pending", None, None


def settle(conn) -> dict:
    """Biten maçlara göre bekleyen seçimleri ve kuponları işaretler. {"picks": n, "coupons": n} döner."""
    rows = conn.execute(
        "SELECT p.day, p.kind, p.match_id, p.market, p.kickoff, m.completed, m.home_goals, m.away_goals, "
        "m.status AS match_status FROM saved_coupon_picks p LEFT JOIN matches m ON m.id = p.match_id "
        "WHERE p.status = 'pending'").fetchall()
    touched, picks_done = set(), 0
    for r in rows:
        status, hg, ag = _pick_outcome(r)
        if status == "pending":
            continue
        conn.execute("UPDATE saved_coupon_picks SET status=?, home_goals=?, away_goals=? "
                     "WHERE day=? AND kind=? AND match_id=?", (status, hg, ag, r["day"], r["kind"], r["match_id"]))
        touched.add((r["day"], r["kind"]))
        picks_done += 1
    now, coupons_done = _now().isoformat(timespec="seconds"), 0
    for day, kind in touched:
        statuses = [x["status"] for x in conn.execute(
            "SELECT status FROM saved_coupon_picks WHERE day=? AND kind=?", (day, kind))]
        new = coupon_status(statuses)
        conn.execute("UPDATE saved_coupons SET status=?, settled_at=? WHERE day=? AND kind=?",
                     (new, None if new == "pending" else now, day, kind))
        coupons_done += new != "pending"
    return {"picks": picks_done, "coupons": coupons_done}


# --- Geçmiş / istatistik -------------------------------------------------------------
def effective_odds(picks: list[dict]) -> float:
    """Kupon oranı; iptal (void) seçimler 1.00 sayılır."""
    total = 1.0
    for p in picks:
        if p["status"] != "void":
            total *= p["odds"]
    return round(total, 2)


def coupon_profit(coupon: dict) -> float | None:
    """STAKE TL'lik kuponun kâr/zararı; bekleyen kupon için None, iptal için 0."""
    if coupon["status"] == "won":
        return round(STAKE * (coupon["effective_odds"] - 1), 2)
    if coupon["status"] == "lost":
        return -STAKE
    return 0.0 if coupon["status"] == "void" else None


def _summary(coupons: list[dict]) -> dict:
    count = lambda s: sum(c["status"] == s for c in coupons)
    won, lost = count("won"), count("lost")
    stake = STAKE * (won + lost)
    returned = round(sum(STAKE * c["effective_odds"] for c in coupons if c["status"] == "won"), 2)
    picks = [p for c in coupons for p in c["picks"] if p["status"] in ("won", "lost")]
    picks_won = sum(p["status"] == "won" for p in picks)
    return {"coupons": len(coupons), "won": won, "lost": lost, "pending": count("pending"), "void": count("void"),
            "hit_rate": won / (won + lost) if won + lost else None,
            "picks_settled": len(picks), "picks_won": picks_won,
            "pick_hit_rate": picks_won / len(picks) if picks else None,
            "stake": stake, "returned": returned, "profit": round(returned - stake, 2),
            "roi": (returned - stake) / stake if stake else None}


def history(conn, days: int = 60) -> dict:
    """Tüm kayıtlı kuponların özeti ve en yeni `days` günün listesi."""
    picks_by = {}
    for r in conn.execute("SELECT * FROM saved_coupon_picks ORDER BY kickoff, match_id"):
        picks_by.setdefault((r["day"], r["kind"]), []).append(
            {k: r[k] for k in ("match_id", "league", "league_name", "kickoff", "home", "away", "market", "odds",
                               "odds_source", "probability", "status", "home_goals", "away_goals")})
    coupons = []
    for r in conn.execute("SELECT * FROM saved_coupons ORDER BY day DESC, kind"):
        c = {k: r[k] for k in ("day", "kind", "total_odds", "total_probability", "odds_source", "status",
                               "created_at", "settled_at")}
        c["picks"] = picks_by.get((c["day"], c["kind"]), [])
        c["effective_odds"] = effective_odds(c["picks"])
        c["profit"] = coupon_profit(c)
        coupons.append(c)
    by_day = {}
    for c in coupons:
        by_day.setdefault(c["day"], {"date": c["day"]})[c["kind"]] = c
    day_list = [{"banko": None, "surprise": None, **d,
                 "profit": round(sum(c["profit"] or 0 for k, c in d.items() if k in KINDS), 2)}
                for d in by_day.values()]
    day_list.sort(key=lambda d: d["date"], reverse=True)
    summary = {kind: _summary([c for c in coupons if c["kind"] == kind]) for kind in KINDS}
    summary["total"] = _summary(coupons)
    return {"stake": STAKE, "summary": summary, "days": day_list[:days], "total_days": len(day_list)}
