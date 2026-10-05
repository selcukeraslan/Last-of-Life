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
| Güncel bahis oranları | iddaa.com maç öncesi bülteni (sitenin herkese açık JSON/XHR uç noktası) |
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

Adil oran = 1/olasılık. Arayüzde iddaa.com oranı ana değer, modelin önerilen oranı ise **Claude oran**
etiketiyle gösterilir. Maç detayında iddaa oranı otomatik doldurulur ve model olasılığına göre beklenen
değer (EV) ile ¼ Kelly hesaplanır; isterseniz alanı değiştirerek başka bir oranı deneyebilirsiniz.

**Günlük Kupon** sekmesi seçilen günün (Türkiye saati, tüm ligler, başlamamış maçlar) iki kuponunu kurar:
- **Banko**: 2-3 maç, maç başı ≥%75, toplam tutma ≥%50, oran ≥1.15; her maçtan tek seçim.
- **Sürpriz**: 3-5 farklı maç, toplam oran ≥15; adaylar EV'ye (olasılık × oran − 1) göre sıralanır, şartı
  sağlayan en olası kombinasyon seçilir.

Kuponda oran olarak eşleşen **iddaa** oranı kullanılır; o pazarda iddaa oranı yoksa **Claude oran**'a düşülür.
Her satırda ve kupon başlığında hangisinin kullanıldığı yazar. Şartı sağlayan seçim yoksa kupon boş döner.
API: `/api/coupons?day=YYYY-MM-DD`. Testler: `.venv/bin/python -m unittest discover -s tests -t .`

**Model** sekmesindeki geriye dönük test her maçı sadece öncesindeki verilerle tahmin edip doğruluğu ölçer.
Parametreler `app/config.py` içindeki `MODEL` sözlüğündedir.

## Dosyalar

```
app/config.py          ayarlar, ligler, model parametreleri
app/scrapers/espn.py   sonuç & fikstür toplayıcı
app/scrapers/iddaa.py  iddaa.com bülten oranları + ESPN maç eşleştirmesi
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
- iddaa.com yalnızca o anda maç öncesi bülteninde yayımlanan oranları döndürür. Uzak tarihli veya henüz
  oran açılmamış ESPN fikstürlerinde iddaa oranı `-` görünür; Claude oranı gösterilmeye devam eder.
- Tahminler istatistiksel tahmindir, kesinlik içermez. Sorumlu oynayın.
