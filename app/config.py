"""Uygulama ayarları. Hepsi lokal, API anahtarı gerekmez."""
import os
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path):
    """Repo dışına sızmayan yerel .env dosyasını okur; gerçek ortam değişkeni her zaman önceliklidir."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_dotenv(BASE_DIR / ".env")

# Doluysa ortak Supabase Postgres (transaction pooler, port 6543); boşsa yerel SQLite dosyası.
DATABASE_URL = os.environ.get("DATABASE_URL") or None
DB_PATH = BASE_DIR / "data" / "iddia.db"
STATIC_DIR = BASE_DIR / "static"

# Lig anahtarları ESPN fikstür sayfalarındaki kısaltmalardır. Ek alanlar:
#   source: "espn" (varsayılan) | "tff" (ESPN'de verisi olmayan lig; resmi TFF sitesinden)
#   kind:   "league" (varsayılan) | "cup" (ligler arası takımların oynadığı Avrupa kupası)
LEAGUES = {
    "tur.1": {"name": "Süper Lig", "country": "Türkiye", "lang": "tr"},
    "eng.1": {"name": "Premier League", "country": "İngiltere", "lang": "en"},
    "esp.1": {"name": "La Liga", "country": "İspanya", "lang": "en"},
    "ita.1": {"name": "Serie A", "country": "İtalya", "lang": "en"},
    "ger.1": {"name": "Bundesliga", "country": "Almanya", "lang": "en"},
    "fra.1": {"name": "Ligue 1", "country": "Fransa", "lang": "en"},
    "tur.2": {"name": "TFF 1. Lig", "country": "Türkiye", "lang": "tr", "source": "tff"},
    "ned.1": {"name": "Eredivisie", "country": "Hollanda", "lang": "en"},
    "por.1": {"name": "Liga Portugal", "country": "Portekiz", "lang": "en"},
    "uefa.champions": {"name": "UEFA Şampiyonlar Ligi", "country": "Avrupa", "lang": "en", "kind": "cup"},
    "uefa.europa": {"name": "UEFA Avrupa Ligi", "country": "Avrupa", "lang": "en", "kind": "cup"},
}


def is_cup(league: str) -> bool:
    return LEAGUES.get(league, {}).get("kind") == "cup"

# Geçmiş veri: bir önceki sezonun başından itibaren çekilir (Elo ısınması için)
HISTORY_START = date(2025, 7, 15)
# Bugünden kaç gün sonrasına kadar fikstür çekilsin
FIXTURE_DAYS_AHEAD = 21

# Not: tam tarayıcı UA dizesi ESPN tarafında bot kontrolüne (HTTP 202, boş gövde) takılıyor
USER_AGENT = "Mozilla/5.0"
REQUEST_DELAY_SEC = 0.4  # kaynak sitelere nazik olmak için

# Model parametreleri
MODEL = {
    "elo_k": 20.0,
    "elo_home_adv": 60.0,
    "elo_new_team": 1450.0,
    "elo_season_regress": 0.25,  # sezon arasında ortalamaya çekme oranı
    "half_life_days": 200.0,  # Poisson güçlerinde zaman ağırlığı yarı ömrü
    "prior_matches": 6.0,  # Poisson güçlerinde lig ortalamasına büzülme
    "elo_weight": 0.7,  # Poisson ile Elo tahminini harmanlama ağırlığı
    "elo_goals_per_point": 0.0045,  # 100 Elo puanı ≈ 0.45 gol üstünlük
    "form_coef": 0.06,  # form farkının log(λ) etkisi
    "news_coef": 0.08,  # haber skoru farkının log(λ) etkisi
    "rest_coef": 0.03,  # yorgunluk (<4 gün dinlenme) cezası
    "dc_rho": -0.06,  # Dixon-Coles düşük skor düzeltmesi
    "margin": 0.05,  # önerilen orana eklenen kâr marjı (%5)
    # iddaa.com oranlarından marjı temizlenmiş olasılıkların harmanlama ağırlığı: 0 = yalnız model,
    # 1 = yalnız piyasa. Oran yoksa model olasılığı aynen kalır. Ağırlığı Model sekmesindeki
    # harmanlı/harmansız karşılaştırma (log-loss taraması) biriktikçe ayarlayın.
    "market_weight": 0.5,
}

NEWS_LOOKBACK_DAYS = 7
