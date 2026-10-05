"""Basit, sözlük tabanlı haber başlığı analizi (Türkçe + İngilizce).

Her başlık için:
  sentiment: -1..1 arası duygu skoru
  injury:    sakatlık / ceza / eksik oyuncu haberi mi (0/1)
"""
import re

_TR_MAP = str.maketrans({"I": "ı", "İ": "i"})


def norm(text: str) -> str:
    return text.translate(_TR_MAP).lower()


POSITIVE = [
    # tr
    "galibiyet", "kazandı", "zafer", "farklı kazan", "geri döndü", "döndü", "iyileşti", "hazır",
    "moral", "lider", "zirve", "seri", "rekor", "şov", "gol yağmuru", "yenilmezlik", "çıkış",
    "takviye", "imza", "müjde", "sevindiren", "formda", "parladı", "coşku", "3 puan",
    # en
    "wins", "won", "victory", "beat", "thrash", "unbeaten", "top of", "boost", "returns",
    "back in training", "fit again", "record", "stunning", "superb", "comeback", "in form",
]
NEGATIVE = [
    # tr
    "mağlubiyet", "yenildi", "kaybetti", "kriz", "sakat", "cezalı", "kırmızı kart", "istifa",
    "kovuldu", "gönderildi", "tepki", "sorun", "şok", "kötü", "düşüş", "puan kaybı", "eksik",
    "forfait", "ameliyat", "yok", "facia", "hezimet", "kabus", "deprem", "gerginlik", "isyan",
    "berabere kaldı", "ıslıklandı", "ayrılık",
    # en
    "defeat", "lost", "loses", "lose", "losing", "beaten", "crisis", "injury", "injured", "ruled out",
    "suspended", "suspension", "sacked", "blow", "setback", "doubt", "sidelined", "out for",
    "pressure", "slump", "winless", "red card", "turmoil", "dropped points", "hamstring",
]
INJURY = [
    "sakat", "sakatlık", "cezalı", "kart cezası", "forma giyemeyecek", "oynayamayacak",
    "oynamayacak", "kadroda yok", "ameliyat", "kadro dışı", "sezonu kapattı", "kırmızı kart",
    "injury", "injured", "ruled out", "suspended", "suspension", "sidelined", "out for",
    "hamstring", "acl", "knock", "doubt for", "miss the", "will miss", "fitness concern",
]
RECOVERY = ["geri döndü", "döndü", "iyileşti", "returns", "back in training", "fit again", "available again"]

_WORD = re.compile(r"\w+", re.U)


def _hits(text: str, words: list[str]) -> int:
    n = 0
    for w in words:
        if " " in w:
            n += text.count(w)
        else:
            # kök eşleşmesi: kelimenin başında geçsin ("sakat" -> "sakatlandı")
            n += len(re.findall(r"\b" + re.escape(w), text))
    return n


def analyze(title: str) -> tuple[float, int]:
    t = norm(title)
    pos = _hits(t, POSITIVE)
    neg = _hits(t, NEGATIVE)
    injury = _hits(t, INJURY) > 0
    if injury and _hits(t, RECOVERY) > 0:
        injury = False  # "sakatlıktan döndü" olumlu haber
        pos += 1
    total = pos + neg
    score = 0.0 if total == 0 else (pos - neg) / total
    return round(score, 3), int(injury)
