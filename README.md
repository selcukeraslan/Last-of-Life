# İddia Oran Öneri

Ücretli/anahtarlı spor API'si kullanmadan, herkese açık sayfalardan veri toplayıp maç sonucu
olasılıkları ve önerilen oranlar üreten lokal web uygulaması.

## Çalıştırma

```sh
cd ~/Desktop/IddiaOran
./run.sh
```

Sonra tarayıcıda: http://127.0.0.1:8000

İlk açılışta veri yoksa (veya son güncelleme 6 saatten eskiyse) arka planda otomatik güncelleme
başlar. İlk tam çekim 6 lig için birkaç dakika sürer, sonraki güncellemeler sadece son günleri çeker.
Arayüzdeki **Verileri güncelle** düğmesi ile elle de tetiklenebilir.

Komut satırından güncelleme:

```sh
.venv/bin/python -m app.updater              # tüm ligler + haberler
.venv/bin/python -m app.updater --league tur.1 --no-news
```

## Veri kaynakları (anahtar gerekmez)

| Veri | Kaynak |
|---|---|
| Maç sonuçları ve fikstür | ESPN fikstür sayfaları (sayfaya gömülü JSON okunur) |
| Puan durumu, form, ev/deplasman performansı, H2H, dinlenme süresi | Yukarıdaki sonuçlardan hesaplanır |
| Haberler, sakatlık/ceza sinyali | Google Haberler RSS (takım başına, son 7 gün) |

Ligler: Süper Lig, Premier League, La Liga, Serie A, Bundesliga, Ligue 1 (`app/config.py` → `LEAGUES`).

## Model

1. **Poisson güçleri**: zaman ağırlıklı (yarı ömür 200 gün), ev/deplasman ayrı hücum-savunma katsayıları.
2. **Elo**: gol farkı ağırlıklı, ev avantajlı, sezon arasında ortalamaya çekilir. Poisson ile harmanlanır.
3. **Form**: son 5 maç ağırlıklı puan ortalaması.
4. **Haber skoru**: başlıklardan sözlük tabanlı duygu skoru + sakatlık/ceza haberi cezası.
5. **Dinlenme**: 4 günden az dinlenen takıma küçük ceza.
6. **Dixon-Coles** düzeltmeli skor matrisi → 1X2, çifte şans, Alt/Üst 1.5/2.5/3.5, KG Var/Yok, skor.

Adil oran = 1/olasılık. Önerilen oran = adil oran + %5 marj. Maç detayında bahis sitesindeki oranı
girerseniz beklenen değer (EV) ve ¼ Kelly hesaplanır.

**Model** sekmesindeki geriye dönük test her maçı sadece öncesindeki verilerle tahmin edip doğruluğu ölçer.
Parametreler `app/config.py` içindeki `MODEL` sözlüğündedir.

## Dosyalar

```
app/config.py          ayarlar, ligler, model parametreleri
app/scrapers/espn.py   sonuç & fikstür toplayıcı
app/scrapers/news.py   Google Haberler RSS toplayıcı
app/sentiment.py       TR/EN başlık duygu + sakatlık analizi
app/model/ratings.py   Elo, Poisson güçleri, form, puan durumu
app/model/predict.py   skor matrisi, pazarlar, oranlar
app/model/engine.py    tüm parametreleri birleştiren motor + geriye dönük test
app/main.py            FastAPI uç noktaları
static/                web arayüzü
data/iddia.db          SQLite veritabanı (otomatik oluşur)
```

## Notlar

- Kaynak sitelerin HTML yapısı değişirse toplayıcı hata verebilir; hata arayüzde gösterilir.
- Tahminler istatistiksel tahmindir, kesinlik içermez. Sorumlu oynayın.
