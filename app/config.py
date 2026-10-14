"""Uygulama ayarları. Hepsi lokal, API anahtarı gerekmez."""
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "iddia.db"
STATIC_DIR = BASE_DIR / "static"

# ESPN fikstür sayfalarındaki lig kısaltmaları
LEAGUES = {
    "tur.1": {"name": "Süper Lig", "country": "Türkiye", "lang": "tr"},
    "eng.1": {"name": "Premier League", "country": "İngiltere", "lang": "en"},
    "esp.1": {"name": "La Liga", "country": "İspanya", "lang": "en"},
    "ita.1": {"name": "Serie A", "country": "İtalya", "lang": "en"},
    "ger.1": {"name": "Bundesliga", "country": "Almanya", "lang": "en"},
    "fra.1": {"name": "Ligue 1", "country": "Fransa", "lang": "en"},
}

# Geçmiş veri bu tarihten itibaren çekilir (2021-22 sezonundan beri; Elo ısınması, H2H ve
# sezonlar arası güç hesapları için). Daha eski tarihe çekilirse eksik kısım bir sonraki
# güncellemede otomatik doldurulur.
HISTORY_START = date(2021, 7, 1)
# Bu sürümden önce veritabanının kapsadığı ilk gün (eski kurulumlarda geriye doldurma sınırı)
LEGACY_HISTORY_START = date(2025, 7, 15)
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
}

NEWS_LOOKBACK_DAYS = 7
