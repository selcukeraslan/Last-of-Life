"""Haber başlıklarından yapılandırılmış bilgi çıkarımı (Türkçe + İngilizce, kural tabanlı).

LLM API'si olmadan çalışır; her karar hangi kalıbın eşleştiğiyle birlikte döner, yani açıklanabilir.

Her başlık tek bir kategoriye ayrılır:
  out        oyuncu yok (sakatlık / sezonu kapattı)       -> kendi gol beklentisi düşer, rakibinki biraz artar
  suspended  cezalı / kırmızı kart                         -> 'out' ile aynı etki
  doubt      şüpheli / oynayıp oynamayacağı belirsiz       -> yarım etki
  return     sakatlıktan dönüş                              -> küçük olumlu etki
  coach_exit teknik direktör gitti                          -> düzen bozulur, iki yönde de olumsuz
  coach_new  yeni teknik direktör                           -> çok küçük olumlu etki (belirsiz)
  turmoil    kriz, tepki, disiplin, mali sorun              -> küçük olumsuz etki
  morale_pos seri, yenilmezlik, liderlik                    -> çok küçük olumlu etki
  morale_neg hezimet, galibiyetsizlik                       -> çok küçük olumsuz etki
  ignored    transfer söylentisi, milli takım, altyapı/kadın takımı, tahmin/canlı yayın, maç sonucu
  neutral    takımla ilgili ama modele etkisi olmayan haber

Etkiler log(λ) cinsindendir: 'att' takımın kendi beklenen golüne, 'opp' rakibin beklenen golüne eklenir.
-0.035 ≈ beklenen golde %3.4 düşüş. Form ve sonuçlar zaten Elo/Poisson/form ile modelde olduğu için
moral haberlerinin etkisi bilerek çok küçüktür (aynı bilgiyi iki kez saymamak için).

Yapamadıkları: oyuncunun önemini (yıldız mı yedek mi) ve mevkisini bilmez; ironi, soru başlıkları ve
başlığın aslında rakip takımla ilgili olmasını her zaman ayırt edemez; sadece başlığı okur, haber metnini değil.
"""
import math
import re
import unicodedata
from datetime import datetime

# kategori -> (att, opp, Türkçe ad)
EFFECTS = {
    "out": (-0.035, 0.015, "Sakat / yok"),
    "suspended": (-0.035, 0.015, "Cezalı"),
    "doubt": (-0.012, 0.005, "Şüpheli"),
    "return": (0.02, -0.008, "Sakatlıktan dönüş"),
    "coach_exit": (-0.025, 0.02, "Teknik direktör ayrıldı"),
    "coach_new": (0.01, 0.0, "Yeni teknik direktör"),
    "turmoil": (-0.015, 0.008, "Kriz / gerginlik"),
    "morale_pos": (0.008, 0.0, "Moral (olumlu)"),
    "morale_neg": (-0.008, 0.0, "Moral (olumsuz)"),
}
IGNORED_LABELS = {
    "opponent": "Rakip takımla ilgili haber (takım sadece maç adı olarak geçiyor)",
    "transfer": "Transfer / sözleşme haberi",
    "international": "Milli takım haberi",
    "other_team": "Altyapı / kadın / B takımı",
    "preview": "Tahmin, canlı yayın veya maç raporu",
}
# Kadro eksikliği haberleri haftalarca geçerlidir; diğerleri 3 günlük yarı ömürle söner
PERSISTENT = {"out", "suspended", "coach_exit", "coach_new"}
HALF_LIFE_DAYS = 3.0
MAX_ABSENCES = 3  # aynı takım için en fazla 3 ayrı eksik oyuncu sayılır
ATT_CAP = (-0.12, 0.05)
OPP_CAP = (-0.03, 0.06)


def fold(text: str) -> str:
    text = text.replace("ı", "i").replace("İ", "i").replace("’", "'")
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).lower()


def _rx(*parts: str) -> re.Pattern:
    return re.compile("|".join(parts))


_COACH = r"(teknik direktor|hoca|calistirici|manager|head coach|coach|boss)"

# Sıra önemli: ilk eşleşen kategori kazanır.
IGNORE_RULES = [
    ("other_team", _rx(r"\bformer\b", r"\bex-", r"\beski (oyuncu|futbolcu)", r"\bkadin", r"\bwomen", r"\bfrauen", r"\bfemenin", r"\bladies", r"\bu1[79]\b", r"\bu2[13]\b",
                       r"\bakademi", r"\bprimavera\b", r"\breserves?\b", r"\bb takimi\b", r"\b[a-z]+ b (host|vs|beat|draw|lose|win)",
                       r"\bvoleybol", r"\bbasketbol", r"\besports?\b")),
    ("international", _rx(r"\bmilli takim", r"\bnational team\b", r"\binternational (break|duty)\b",
                          r"\bfor (england|france|spain|italy|germany|portugal|brazil|argentina|turkiye|turkey|"
                          r"scotland|wales|netherlands|belgium|croatia|norway|denmark|poland|usa)\b",
                          r"\b(france|turkiye|turkey|italy|england|spain|germany) and (france|turkiye|turkey|italy|england|spain|germany)\b",
                          r"\bworld cup qualif", r"\bdunya kupasi elem", r"\bnations league\b", r"\buluslar ligi\b")),
    ("transfer", _rx(r"\btransfer", r"\bsign(s|ing|ed)?\b", r"\btarget", r"\bmonitor", r"\blinked\b", r"\bbid\b",
                     r"\bloan\b", r"\bkiralik", r"\bteklif", r"\bilgileniyor", r"\bgundeminde", r"\bto land\b",
                     r"\bset to join\b", r"\bcontract\b", r"\bsozlesme", r"\bimza", r"\bbonservis", r"\brenew",
                     r"\bextension\b", r"\bgolden boy\b", r"\bshortlist", r"\baward\b", r"\bodul", r"\bcommitment\b",
                     r"\bboyhood\b", r"\bbuys?\b.*\bclub\b", r"\bsatin al")),
    ("preview", _rx(r"\bpredictions?\b", r"\bbetting\b", r"\btips\b", r"\bodds\b", r"\bpreview\b", r"\blive\b",
                    r"\bcanli\b", r"\bplay-by-play\b", r"\bfinal score\b", r"\bhighlights\b", r"\bozet", r"\btahmin",
                    r"\biddaa\b", r"\bhangi kanalda\b", r"\bsaat kacta\b", r"\bne zaman\b", r"\bmuhtemel 11",
                    r"\bpossible lineups?\b", r"\bpredicted lineups?\b", r"\bpaper round\b")),
]

EVENT_RULES = [
    ("coach_exit", _rx(rf"\b(kovuldu|gorevden alindi|gorevine son|istifa|yollar(ini)? ayir|ayrildi)\b.*{_COACH}",
                       rf"{_COACH}.*\b(kovuldu|gorevden alindi|gorevine son|istifa|yollar(ini)? ayir|ayrildi)",
                       r"\bsacked\b", r"\bfired\b", rf"\b(parted company|parts? ways|steps? down|resigns?|dismissed)\b.*{_COACH}",
                       rf"{_COACH}.*\b(parted company|parts? ways|steps? down|resigns?|dismissed)\b")),
    ("coach_new", _rx(rf"\byeni {_COACH}", rf"{_COACH}.*\b(anlasti|anlasma saglandi|goreve basladi|resmen)\b",
                      r"\bappointed\b", rf"\bnew {_COACH}", r"\btakes charge\b", r"\bnamed (as )?(new )?(manager|head coach)\b")),
    ("return", _rx(r"\bgeri dondu", r"\bdonuyor\b", r"\biyilesti", r"\btakima dondu", r"\bantrenmanlara (basladi|dondu)",
                   r"\bsahalara don", r"\breturns?\b(?! to)(?!.*\b(league|lig)\b)", r"\breturns? to (training|action|the squad|fitness)\b",
                   r"\breturns?\b.*\bafter injury\b", r"\bboost after\b", r"\bback in training\b", r"\bfit again\b",
                   r"\bavailable again\b", r"\bback from injury\b", r"\bcleared to play\b", r"\bboost as\b")),
    ("doubt", _rx(r"\bsuphe", r"\boynayabilecek mi", r"\bdurumu belirsiz", r"\bdoubt", r"\bfitness (concern|test|worry)",
                  r"\brace against time\b", r"\blate fitness\b", r"\btouch and go\b", r"\bknock\b", r"\bfacing a race\b")),
    ("suspended", _rx(r"\bcezali", r"\bkart cezasi", r"\bkirmizi kart", r"\bmen cezasi", r"\bsuspend", r"\bsuspension\b",
                      r"\bbanned\b", r"\bban\b", r"\bred card\b", r"\bsent off\b")),
    ("out", _rx(r"\bsakat", r"\bsezonu kapatti", r"\bameliyat", r"\bforma giyemeyecek", r"\boynayamayacak",
                r"\boynamayacak", r"\bkadroda yok", r"\bkadroya alinmadi", r"\bkadro disi", r"\binjur", r"\bruled out\b",
                r"\bsidelined\b", r"\bout for\b", r"\bwill miss\b", r"\b(set )?to miss\b", r"\bmisses\b", r"\bhamstring",
                r"\bacl\b", r"\bankle\b", r"\bknee\b", r"\bsurgery\b", r"\bfracture", r"\bcalf\b", r"\bgroin\b",
                r"\bconcussion\b", r"\bmuscle\b", r"\bblow\b")),
    ("turmoil", _rx(r"\bkriz", r"\bisyan", r"\btepki", r"\bgerginlik", r"\bkavga", r"\bprotest", r"\bunrest\b",
                    r"\bturmoil\b", r"\bcrisis\b", r"\bfined\b", r"\bpunished\b", r"\bdisiplin", r"\bdressing room\b",
                    r"\bsoyunma odasi", r"\bunder[- ]pressure\b", r"\bultimatum\b", r"\bmaas", r"\bunpaid\b",
                    r"\bmali (kriz|sorun)", r"\bihtar", r"\bislik", r"\byuhalandi", r"\bbaskan.*istifa")),
    # "X beat Y" gibi tek maç sonuçları bilerek yok: kimin kazandığı başlıktan güvenilir çıkmaz ve sonuçlar
    # zaten form/Elo ile modelde. Sadece süregelen durumu anlatan ifadeler sayılır.
    ("morale_neg", _rx(r"\bwinless\b", r"\blosing (streak|run)\b", r"\bgalibiyet hasreti", r"\bgalibiyet yuzu",
                       r"\bhezimet", r"\bkabus gibi", r"\bhumiliat", r"\bslump", r"\brelegation (battle|zone|fight)\b",
                       r"\bkume dusme hattı", r"\bkotu gidis", r"\bwithout a win\b", r"\bbottom of\b")),
    ("morale_pos", _rx(r"\bunbeaten\b", r"\bwinning (streak|run)\b", r"\byenilmez", r"\bgalibiyet serisi",
                       r"\bseri(yi|sini)? (surdur|uzat)", r"\bstraight wins?\b", r"\bin a row\b", r"\bzirvede\b",
                       r"\bliderli", r"\btop of the (table|league)\b", r"\bmoral(i|ler)? (yuksek|depo)", r"\bin form\b")),
]

_NAME = re.compile(r"[A-ZÇĞİÖŞÜÁÉÍÓÚÑÄËÏÖÜ][\w'’.\-]+(?:\s+[A-ZÇĞİÖŞÜÁÉÍÓÚÑÄËÏÖÜ][\w'’.\-]+)*")
_NAME_STOP = {"fc", "fk", "sk", "afc", "the", "a", "an", "premier", "league", "lig", "super", "süper", "la", "liga",
              "serie", "bundesliga", "ligue", "uefa", "champions", "europa", "cup", "kupa", "kupası", "milli", "takım",
              "boost", "blow", "news", "injury", "update", "breaking", "son", "dakika", "flaş", "resmi", "official",
              "still", "when", "goalkeeper", "hopefully", "işte", "next", "why", "how", "what", "who", "mp", "roma",
              "captain", "kaptan", "defender", "striker", "midfielder", "winger", "forward"}


def _player(title: str, team: str) -> str | None:
    """Başlıktaki olası oyuncu adı (yalnızca tekrar eden haberleri birleştirmek için; en iyi tahmin)."""
    team_tokens = {fold(t) for t in re.split(r"[\s\-]+", team) if len(t) > 2}
    for m in _NAME.finditer(title):
        words = [w.strip("'’.-") for w in m.group(0).split()]
        words = [re.split(r"['’]", w)[0] for w in words]  # "Galatasaray'da" -> "Galatasaray"
        words = [w for w in words if fold(w) not in team_tokens and fold(w) not in _NAME_STOP and len(w) > 2]
        if not words:
            continue
        return " ".join(words)
    return None


_TEAM_STOP = {"fc", "fk", "sk", "afc", "cf", "ac", "as", "ss", "sc", "club", "de", "the", "united", "city", "real",
              "and", "hove", "albion", "spor"}
_MATCH_AFTER = r"(mac(i|in|ina|inda|indan)?|clash|game|match|tie|fixture|opponents?|deplasman(i|inda)?)\b"
_MATCH_BEFORE = r"\b(against|vs\.?|v\.?|face|faces|facing|host|hosts|visit|visits|karsisinda|ile)\s+"


def _team_tokens(*names: str) -> list[str]:
    out = []
    for n in names:
        if n:
            out += [t for t in fold(n).replace("-", " ").split() if len(t) > 2 and t not in _TEAM_STOP]
    return out


def _mentioned_as_opponent(t: str, tokens: list[str]) -> str | None:
    """Takım başlıkta sadece maç adı olarak geçiyorsa ("X maçında", "doubt for X clash", "against X")
    haber aslında rakip takımla ilgilidir."""
    for tok in tokens:
        tok = re.escape(tok)
        m = re.search(rf"\b{tok}\w*(\s+\w+)?\s+{_MATCH_AFTER}", t) or re.search(rf"{_MATCH_BEFORE}(\w+\s+)?{tok}", t)
        if m:
            return m.group(0)
    return None


_LEAGUE_RETURN = re.compile(r"\b(premier league|la liga|bundesliga|serie a|ligue 1|super lig|league|lig|cup|kupa|"
                            r"season|sezon)\b\W+(\w+\W+)?(return|back|donus|geri don)")


def classify(title: str, team: str = "", alias: str | None = None) -> dict:
    """Bir başlığı sınıflandırır. Dönen sözlük: category, label, rule (eşleşen ifade), player, att, opp."""
    t = fold(title)
    tokens = _team_tokens(team, alias)
    for cat, rx in IGNORE_RULES:
        m = rx.search(t)
        # Milli takımdan dönen/çıkarılan oyuncunun kulüp maçındaki durumu yine de ilgili olabilir
        if m and not (cat == "international" and re.search(r"\bmac(i|in|ina|inda)\b", t)):
            return {"category": "ignored", "kind": cat, "label": IGNORED_LABELS[cat], "rule": m.group(0),
                    "player": None, "att": 0.0, "opp": 0.0}
    for cat, rx in EVENT_RULES:
        m = rx.search(t)
        if m:
            opp_hit = _mentioned_as_opponent(t, tokens) if tokens else None
            if opp_hit:
                return {"category": "ignored", "kind": "opponent", "label": IGNORED_LABELS["opponent"],
                        "rule": opp_hit, "player": None, "att": 0.0, "opp": 0.0}
            if cat == "return" and _LEAGUE_RETURN.search(t):
                continue  # "Premier League return", "Lig'e dönüş": oyuncu değil, lig/organizasyon haberi
            att, opp, label = EFFECTS[cat]
            return {"category": cat, "kind": cat, "label": label, "rule": m.group(0)[:40],
                    "player": _player(title, team) if cat in ("out", "suspended", "doubt", "return") else None,
                    "att": att, "opp": opp}
    if re.search(r"\b\d+\s*[-–]\s*\d+\b", t):
        return {"category": "ignored", "kind": "preview", "label": IGNORED_LABELS["preview"], "rule": "skor",
                "player": None, "att": 0.0, "opp": 0.0}
    return {"category": "neutral", "kind": "neutral", "label": "Etkisiz", "rule": None, "player": None,
            "att": 0.0, "opp": 0.0}


def summarize(team: str, rows: list[dict], at: datetime, parse_ts, alias: str | None = None) -> dict:
    """Bir takımın son haberlerinden toplam etki. rows: title, link, source, published (en yeni önce)."""
    items, events, seen = [], [], {}
    returned: dict[str, datetime] = {}
    classified = []
    for r in rows:
        c = classify(r["title"], team, alias)
        ts = parse_ts(r["published"])
        classified.append((r, c, ts))
        if c["category"] == "return" and c["player"]:
            returned[c["player"]] = max(ts, returned.get(c["player"], ts))
    absences = 0
    for r, c, ts in classified:
        age = max(0.0, (at - ts).total_seconds() / 86400)
        w = 1.0 if c["category"] in PERSISTENT else 0.5 ** (age / HALF_LIFE_DAYS)
        status = None
        if c["category"] in EFFECTS:
            key = (c["category"], c["player"] or " ".join(fold(r["title"]).split()[:5]))
            if c["category"] in ("out", "suspended", "doubt") and c["player"] in returned and returned[c["player"]] > ts:
                status = "sonradan döndüğü için sayılmadı"
            elif key in seen:
                status = "aynı olay, tekrar sayılmadı"
            elif c["category"] in ("out", "suspended") and absences >= MAX_ABSENCES:
                status = f"en fazla {MAX_ABSENCES} eksik sayılır"
            else:
                seen[key] = True
                absences += c["category"] in ("out", "suspended")
                events.append({"category": c["category"], "label": c["label"], "player": c["player"],
                               "att": round(c["att"] * w, 4), "opp": round(c["opp"] * w, 4), "weight": round(w, 2),
                               "title": r["title"]})
        items.append({**{k: r[k] for k in ("title", "link", "source", "published")},
                      "category": c["category"], "kind": c["kind"], "label": c["label"], "rule": c["rule"],
                      "player": c["player"], "counted": c["category"] in EFFECTS and status is None,
                      "note": status, "att_pct": _pct(c["att"] * w) if c["category"] in EFFECTS and status is None else 0.0})
    att = max(ATT_CAP[0], min(ATT_CAP[1], sum(e["att"] for e in events)))
    opp = max(OPP_CAP[0], min(OPP_CAP[1], sum(e["opp"] for e in events)))
    relevant = sum(1 for i in items if i["category"] != "ignored")
    counts: dict[str, int] = {}
    for e in events:
        counts[e["category"]] = counts.get(e["category"], 0) + 1
    return {"att": round(att, 4), "opp": round(opp, 4), "att_pct": _pct(att), "opp_pct": _pct(opp),
            "events": events, "counts": counts, "relevant": relevant, "total": len(items),
            "absences": counts.get("out", 0) + counts.get("suspended", 0), "items": items}


def _pct(x: float) -> float:
    return round((math.exp(x) - 1) * 100, 1)
