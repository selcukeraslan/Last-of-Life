"""Google için sunucu tarafında üretilen maç sayfaları, sitemap ve robots."""
import re
from datetime import datetime, timezone
from html import escape

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import HTMLResponse

from . import ops
from .model.coupons import TZ

router = APIRouter()
SITE = "https://iddia-oran.vercel.app"
CACHE = "public, s-maxage=900, stale-while-revalidate=3600"
AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
_TR = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosuCGIOSUaiu")
DISCLAIMER = "18+ · Tahminler garanti değildir, yatırım tavsiyesi değildir. Sorumlu oynayın."


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.translate(_TR).lower()).strip("-")


def match_path(m: dict) -> str:
    return f"/mac/{slugify(m['home'])}-{slugify(m['away'])}-{m['id']}"


def _kickoff(m: dict) -> datetime:
    return datetime.fromisoformat(str(m["kickoff"]).replace("Z", "+00:00")).astimezone(TZ)


def _pct(p) -> str:
    return "-" if p is None else f"%{round(p * 100)}"


def _rows(m: dict, keys: list[tuple[str, str]]) -> str:
    mk, io = m.get("markets") or {}, m.get("iddaa_odds") or {}
    out = ""
    for key, label in keys:
        v = mk.get(key)
        if not v:
            continue
        out += (f"<tr><td>{escape(label)}</td><td>{_pct(v.get('p'))}</td>"
                f"<td>{io.get(key) or '-'}</td><td>{v.get('suggested') or '-'}</td></tr>")
    return out


def summary(m: dict) -> str:
    mk = m.get("markets") or {}
    h, a = m["home"], m["away"]
    txt = ""
    if all(k in mk for k in ("1", "X", "2")):
        best = max(("1", "X", "2"), key=lambda k: mk[k]["p"])
        who = {"1": f"{h} galibiyeti", "X": "beraberlik", "2": f"{a} galibiyeti"}[best]
        txt += f"Modelimize göre en olası sonuç {who} (%{round(mk[best]['p'] * 100)}). "
    if "Ü2.5" in mk:
        txt += f"2,5 üstü olasılığı {_pct(mk['Ü2.5']['p'])}"
        txt += f", karşılıklı gol olasılığı {_pct(mk['KG Var']['p'])}. " if "KG Var" in mk else ". "
    if m.get("scores"):
        txt += f"En olası skor {m['scores'][0]['score']}."
    return txt.strip() or f"{h} - {a} maçı için model tahmini hazırlanıyor."


def render(m: dict) -> str:
    ko = _kickoff(m)
    date_tr = f"{ko.day} {AYLAR[ko.month - 1]} {ko.year}"
    h, a = escape(m["home"]), escape(m["away"])
    title = f"{h} - {a} tahmini, oranlar ({date_tr})"
    url = SITE + match_path(m)
    desc = escape(f"{m['home']} - {m['away']} maçı için 1X2, alt/üst ve KG olasılıkları, iddaa ve Claude oranları. {summary(m)}")[:300]
    ld = {"@context": "https://schema.org", "@type": "SportsEvent", "name": f"{m['home']} - {m['away']}",
          "startDate": ko.isoformat(), "url": url, "eventStatus": "https://schema.org/EventScheduled",
          "homeTeam": {"@type": "SportsTeam", "name": m["home"]}, "awayTeam": {"@type": "SportsTeam", "name": m["away"]},
          "location": {"@type": "Place", "name": m.get("league_name") or "Futbol"}}
    import json
    ldj = json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")
    head = "<tr><th>Pazar</th><th>Olasılık</th><th>İddaa</th><th>Claude</th></tr>"
    tables = "".join(f"<h2>{t}</h2><table>{head}{r}</table>" for t, r in (
        ("Maç sonucu (1X2)", _rows(m, [("1", f"{m['home']} (1)"), ("X", "Beraberlik (X)"), ("2", f"{m['away']} (2)")])),
        ("Alt / Üst", _rows(m, [("A1.5", "1,5 Alt"), ("Ü1.5", "1,5 Üst"), ("A2.5", "2,5 Alt"), ("Ü2.5", "2,5 Üst"), ("A3.5", "3,5 Alt"), ("Ü3.5", "3,5 Üst")])),
        ("Karşılıklı gol", _rows(m, [("KG Var", "KG Var"), ("KG Yok", "KG Yok")]))) if r)
    score = ""
    if m.get("scores"):
        score = "<h2>En olası skor</h2><p>" + " · ".join(f"<b>{escape(str(s['score']))}</b> {_pct(s['p'])}" for s in m["scores"][:3]) + "</p>"
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<meta name="description" content="{desc}"><link rel="canonical" href="{url}">
<meta property="og:type" content="article"><meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}"><meta property="og:url" content="{url}"><meta property="og:locale" content="tr_TR">
<meta name="twitter:card" content="summary"><meta name="twitter:title" content="{title}"><meta name="twitter:description" content="{desc}">
<link rel="stylesheet" href="/static/theme.css">
<script type="application/ld+json">{ldj}</script>
<style>body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.5 system-ui,sans-serif}}
main{{max-width:720px;margin:0 auto;padding:20px 16px}}h1{{font-size:1.5rem}}h2{{font-size:1.1rem;margin-top:1.5rem}}
table{{width:100%;border-collapse:collapse;background:var(--panel);border-radius:var(--r-md)}}
td,th{{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left}}th{{color:var(--muted);font-weight:500}}
.cta{{display:inline-block;margin:1.5rem 0;padding:12px 18px;background:var(--accent);color:#fff;border-radius:var(--r-md);text-decoration:none;font-weight:600}}
.muted{{color:var(--muted)}}</style></head><body><main>
<p class="muted">{escape(m.get('league_name') or '')} · {date_tr} {ko:%H:%M}</p>
<h1>{title}</h1><p>{escape(summary(m))}</p>{tables}{score}
<a class="cta" href="/?match={escape(str(m['id']))}">Detaylı analiz →</a>
<p class="muted">{DISCLAIMER}</p></main></body></html>"""


def _load(match_id: str) -> dict:
    from .main import match  # döngüsel içe aktarmayı önlemek için geç
    try:
        return match(match_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(404, "Maç bulunamadı")


@router.get("/mac/{slug}")
def match_page(slug: str):
    mid = slug.rsplit("-", 1)[-1]
    m = _load(mid)
    html = ops.cached(("seo-match", mid), lambda: render(m))
    return HTMLResponse(html, headers={"Cache-Control": CACHE})


def _sitemap() -> str:
    from .config import LEAGUES
    from .main import _upcoming
    urls = [SITE + "/"]
    for lg in LEAGUES:
        try:
            urls += [SITE + match_path(m) for m in _upcoming(lg, 14)]
        except Exception:
            continue
    body = "".join(f"<url><loc>{escape(u)}</loc></url>" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'


@router.get("/sitemap.xml")
def sitemap():
    return Response(ops.cached(("sitemap",), _sitemap), media_type="application/xml", headers={"Cache-Control": CACHE})


@router.get("/robots.txt")
def robots():
    return Response(f"User-agent: *\nAllow: /\nDisallow: /api/\nSitemap: {SITE}/sitemap.xml\n",
                    media_type="text/plain", headers={"Cache-Control": CACHE})
