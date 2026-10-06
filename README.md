# İddia Oran Öneri

Ücretli/anahtarlı spor API'si kullanmadan, herkese açık sayfalardan veri toplayıp maç sonucu
olasılıkları ve önerilen oranlar üreten lokal web uygulaması.

## Çalıştırma

```sh
cd ~/Desktop/IddiaOran
./run.sh
```

Sonra tarayıcıda: http://127.0.0.1:8000

`DATABASE_URL` tanımlı değilse yerel SQLite (`data/iddia.db`) kullanılır; bu modda ilk açılışta veri yoksa
(veya son güncelleme 6 saatten eskiyse) arka planda tam güncelleme başlar. İlk tam çekim 11 lig için birkaç
dakika sürer, sonrakiler sadece son günleri çeker.

Komut satırından (ağır) tam güncelleme:

```sh
.venv/bin/python -m app.updater              # tüm ligler + haberler + iddaa oranları
.venv/bin/python -m app.updater --league tur.1 --no-news
```

## Ortak veritabanı (Supabase) ve güncelleme akışı

Herkese açık (Vercel) kurulumda veri ortak Supabase Postgres'tedir; biri güncelleyince herkes aynı veriyi ve
"X dk önce güncellendi" bilgisini görür.

- `DATABASE_URL`: Supabase **transaction pooler** adresi (`...pooler.supabase.com:6543`). Ortam değişkeni
  (Vercel, GitHub secret) veya repo dışı `.env` (bkz. `.env.example`, gitignore'da) olarak verilir.
  Tanımlıysa uygulama Postgres, değilse SQLite kullanır. Testler `.env`'yi yok sayıp her zaman SQLite kullanır.
- Şema: `supabase/migrations/` (`supabase db push --db-url <session-pooler-url>`). Bir kerelik yerel veri
  aktarımı: `python scripts/import_sqlite_to_postgres.py --sqlite data/iddia.db`.
- `meta` tablosu: `last_updated_at` (son başarılı güncelleme), `update_lock` (kilidin bitiş zamanı; zaman aşımlı).
- **Verileri güncelle** (`POST /api/update`): istek içinde senkron, hızlı artımlı güncelleme (iddaa oranları +
  ESPN son 3 gün). Arka plan thread'i yoktur; kilit eşzamanlı çalışmayı engeller, son güncellemeden sonra
  10 dk bekleme vardır (`status`: `updated` | `cooldown` | `busy` | `error`). Durum: `GET /api/update/status`.
- Ağır tam güncelleme + haberler: `.github/workflows/update.yml` her 30 dk (`workflow_dispatch` ile elle de);
  `DATABASE_URL` GitHub secret'ından okunur.

## Veri kaynakları (anahtar gerekmez)

| Veri | Kaynak |
|---|---|
| Maç sonuçları ve fikstür | ESPN fikstür sayfaları (sayfaya gömülü JSON okunur) |
| Güncel bahis oranları | iddaa.com maç öncesi bülteni (sitenin herkese açık JSON/XHR uç noktası) |
| Puan durumu, form, ev/deplasman performansı, H2H, dinlenme süresi | Yukarıdaki sonuçlardan hesaplanır |
| Haberler, sakatlık/ceza sinyali | Google Haberler RSS (takım başına, son 7 gün) |

Ligler: Süper Lig, Premier League, La Liga, Serie A, Bundesliga, Ligue 1, TFF 1. Lig, Eredivisie, Liga Portugal,
UEFA Şampiyonlar Ligi, UEFA Avrupa Ligi (`app/config.py` → `LEAGUES`).

### TFF 1. Lig ve Avrupa kupaları

- **TFF 1. Lig (`tur.2`)**: ESPN bu lig için sluğu listeliyor ama hiç maç/takım döndürmüyor. Veri resmi TFF
  sitesinden (`app/scrapers/tff.py`, `hafta=N` sayfaları; TSİ → UTC) okunur. Önceki sezon çekilmediği için
  sezon başında veri azdır (güven puanı bunu düşük gösterir). Kulüp adları `CLUB_NAMES` tablosundadır; yeni
  sezonda yükselen takımlar genel temizlemeyle adlandırılır, gerekirse tabloya eklenir.
- **Avrupa kupaları (`uefa.champions`, `uefa.europa`)**: `app/model/european.py`. Ligler arası güç =
  takımın kendi lig Elo'su + lig ofseti; ofsetler UEFA sırasına dayanan yaklaşık önsellerle başlar ve
  kupadaki ligler arası maçlardan MAP ile güncellenir; ardından kupa sonuçları takım başına Elo düzeltmesi
  ekler. Ligi bizde olmayan takımlar (Celtic, Club Brugge…) "diğer" grubunda 1500 civarından başlar.
  Haberler takımın kendi liginden alınır; kupalar için ayrıca haber çekilmez ve geriye dönük test yapılmaz.
- Tam geçmiş çekimi yalnız `python -m app.updater` / GitHub Actions cron'unda çalışır; web isteği
  (`/api/update`) yalnız hızlı güncellemeyi çalıştırır ve lig çekimleri için 120 sn sınırı vardır.

## iddaa oranlarıyla harmanlama

`app/model/blend.py`: iddaa.com oranından marj temizlenir (1X2 üçlü, Alt/Üst 1.5/2.5/3.5 ve KG ikili gruplar:
`1/oran`, grup toplamına bölünür) ve model olasılığıyla `p = (1-w)·p_model + w·p_piyasa` harmanlanır;
`w = MODEL["market_weight"]` (`app/config.py`, 0 = yalnız model). Oran yoksa (veya grup eksik/tutarsızsa)
model olasılığı aynen kalır. Çifte şans harmanlı 1X2'den türetilir; öneri, güven, "Claude oran" ve günlük
kuponlar harmanlı olasılığı kullanır. Yanıtlarda her pazarda `model_p` / `market_p`, tahminde `blend` alanı vardır.

**Backtest karşılaştırması:** geçmiş iddaa oranı tutulmadığı için (`iddaa_odds` her senkronda yeniden yazılır)
oranlar bundan sonra `odds_log` tablosuna kaydedilir (maç başına pazar başı ilk ve maçtan önceki son oran;
her oran senkronunda otomatik). Model sekmesindeki test, kayıtlı maçlarda model / harmanlı / yalnız piyasa
olasılıklarını Brier, log-loss ve isabet ile karşılaştırır; ayrıca `market_weight` için ağırlık taraması verir.
Kayıt biriktikçe (birkaç yüz sonuçlanmış maç) ağırlık bu taramaya göre ayarlanmalıdır.
Şema: `supabase/migrations/20261006110000_odds_log.sql` (deploy'dan önce uygulanmalı; uygulanmazsa oran
senkronu bozulmaz, kayıt atlanır ve `meta.odds_log_error` doldurulur).

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

**Kupon Geçmişi** sekmesi: günün Banko ve Sürpriz kuponu (gün + tür başına bir kez, ilk üretildiği haliyle) `saved_coupons` /
`saved_coupon_picks` tablolarına dondurulur — bugünün kuponu `/api/coupons` ile ilk üretildiğinde veya tam güncellemede
(cron). Maç sonuçları gelince (hızlı ve tam güncelleme akışında) her seçim ve kupon `Tuttu` / `Yattı` / `Bekliyor` (`İptal`:
ertelenen/iptal maç, oran 1.00) işaretlenir; tek seçim yattıysa kupon hemen yatmıştır. Sekmede banko tutma oranı, sürpriz
tutma sayısı, "her gün her kupona 100 TL yatırsaydın" kâr/zarar + ROI (yalnız sonuçlanan kuponlar, kayıtlı oranla) ve günlük
liste vardır. API: `GET /api/coupon-history?days=60`. Kod: `app/model/coupon_history.py`.

**Değerli Oranlar** sekmesi yaklaşan (başlamamış) maçlarda modelin olasılığını iddaa.com oranıyla karşılaştırır;
EV = olasılık × oran − 1 > 0 olan seçimleri EV'ye göre sıralar (pazar, seçim, model %, iddaa oranı, örtük %,
EV %, maç/lig/saat). Min. olasılık ve min. EV filtreleri vardır; iddaa oranı olmayan pazar/maç listeye girmez,
liste boşsa nedeni mesajla açıklanır. API: `/api/value-bets?days=7&min_prob=0.3&min_ev=0.05` (oran ve EV 0-1 aralığında).

**Kuponum** sekmesi kendi kuponunuzu kurar: maç kartlarındaki **＋ Kupona ekle** düğmesi modelin önerisini ekler;
maç detayındaki her pazar (1X2, çifte şans, Alt/Üst 1.5-2.5-3.5, KG) için ayrı düğme vardır. Kuponda toplam oran
(iddaa oranı varsa o, yoksa Claude oran), model tutma ihtimali (seçim olasılıklarının çarpımı), EV ve
yatırılan tutardan olası kazanç gösterilir; aynı maçtan birden fazla seçim ya da birlikte tutamayacak seçimler
(örn. 1 ve X) uyarılır. Kupon sunucuya gitmez, tarayıcının `localStorage`'ında (`iddiaoran.slip.v1`) durur; sekme
açılınca oranlar `/api/match/{id}` ile yenilenir. Hesaplar `static/slip-calc.js` (saf JS, `node --test tests/js/`;
`unittest discover` de node varsa bunu çalıştırır), arayüz `static/slip.js` + `static/slip.css`.

**Model** sekmesindeki geriye dönük test her maçı sadece öncesindeki verilerle tahmin edip doğruluğu ölçer.
Parametreler `app/config.py` içindeki `MODEL` sözlüğündedir.

## Telegram kanalı (günlük kupon + sonuç)

`app/telegram_bot.py` Telegram Bot API'sini (kütüphanesiz, HTTP) kullanır. Türkiye saatiyle 09:00-15:00
arasında o günün **banko + sürpriz** kuponunu kanala gönderir; kuponun tüm maçları bitince sonucu
(✅/❌, skorlar) kupon mesajına yanıt olarak yazar. Aynı gün/tür ikinci kez gönderilmez: `telegram_posts`
tablosundaki (gün, tür) kaydı önce alınır, gönderim başarısız olursa bırakılır ve sonraki çalıştırmada
tekrar denenir. `TELEGRAM_BOT_TOKEN` veya `TELEGRAM_CHAT_ID` tanımlı değilse hiçbir şey yapmadan çıkar.

Kurulum (bir kez):
1. Telegram'da **@BotFather** → `/newbot` ile bot oluşturun, verdiği **token**'ı kopyalayın.
2. Bir **kanal** oluşturun (herkese açık ise `@kanal_adi`, özel ise sayısal kimlik `-100…` kullanılır).
3. Botu kanala **yönetici** olarak ekleyin ("Mesaj gönder" yetkisi yeterli).
4. Kanal kimliği: herkese açık kanalda `@kanal_adi`; özel kanalda kanala bir mesaj atıp
   `https://api.telegram.org/bot<TOKEN>/getUpdates` yanıtındaki `chat.id` değerini (`-100…`) alın.
5. GitHub → repo → Settings → Secrets and variables → Actions: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
   ekleyin (`DATABASE_URL` zaten var).
6. Supabase'e `supabase/migrations/20261006000000_telegram_posts.sql` migration'ını uygulayın
   (yerel SQLite'ta tablo otomatik oluşur).
7. İlk deneme: Actions → "Telegram kupon" → *Run workflow* (`force` işaretli).

Workflow (`.github/workflows/telegram.yml`) her saatin 20. dakikasında çalışır; zamanlanmış workflow'lar
yalnızca varsayılan dalda (main) tetiklenir. Yerelde: `python -m app.telegram_bot --dry-run` mesajı göndermeden
ekrana yazar; `--force` sabah penceresini, `--day YYYY-MM-DD` günü değiştirir.
## PWA (ana ekrana ekle)

Site yüklenebilir bir PWA'dır (Android/Chrome "Uygulamayı yükle", iOS Safari "Ana Ekrana Ekle").

- `app/pwa.py`: `/manifest.webmanifest` (`application/manifest+json`) ve `/sw.js` (kökten, kapsam `/`; `no-cache`).
  Vercel'de tüm yollar FastAPI'ye gittiği için başlıklar burada ayarlanır.
- `app/sw.js` (service worker şablonu): `/` + `static/` önbelleğe alınır (cache-first); önbellek adı `static/`
  içeriğinin özetinden türetilir, yani statik dosya değişince otomatik yeni sürüm kurulur ve "Yeni sürüm hazır" bandı çıkar.
  `/api` GET istekleri network-first: ağ yok/yavaş (8 sn)/5xx ise son kaydedilen yanıt gösterilir ve "kayıtlı veri
  gösteriliyor" bandı çıkar (`/api/update*` hiç önbelleğe alınmaz). ESPN takım logoları cache-first.
- `static/pwa.js`: kayıt + çevrimdışı/güncelleme bandı. `static/icons/`: 192/512 + maskable + apple-touch-icon;
  `python scripts/make_pwa_icons.py` ile yeniden üretilir (saf Python).
- Yerelde de çalışır (`localhost` güvenli bağlam sayılır). Sorun olursa tarayıcıda DevTools → Application → Service Workers.
**Oran hareketi**: her iddaa çekiminde değişen oranlar `iddaa_odds_history` tablosuna zaman damgalı satır olarak
eklenir (oran aynıysa yazılmaz; güncel oran yine `iddaa_odds`'tadır). İlk kayıt "açılış", son kayıt güncel
orandır; açılış iddaa.com'un gerçek açılış oranı değil, bizim ilk gördüğümüz orandır. Oran hücrelerinde
`2.10 → 1.85 ↓`, maç detayında pazar başına geçmiş, Maçlar sekmesinde açılışa göre %10+ düşenlerin
**Oran düşüşü** listesi görünür. Bitmiş maçların geçmişi (bültenden çıkmış ve son maç saati 30 günden eski)
her çekimde temizlenir. API: `/api/odds/history/{match_id}`, `/api/odds/drops?min_pct=10&league=tur.1`;
`/api/upcoming`, `/api/picks` ve `/api/match/{id}` yanıtlarında `iddaa_movement` (yalnız değişen pazarlar).
Yeni tablo için `supabase/migrations/20261006000000_iddaa_odds_history.sql` deploy'dan önce uygulanmalıdır.

## Dosyalar

```
app/config.py          ayarlar, ligler, model parametreleri
app/scrapers/espn.py   sonuç & fikstür toplayıcı
app/scrapers/tff.py    TFF 1. Lig toplayıcı (ESPN'de verisi yok)
app/model/european.py  Avrupa kupaları için ligler arası güç modeli
app/scrapers/iddaa.py  iddaa.com bülten oranları + ESPN maç eşleştirmesi
app/odds_history.py    oran geçmişi: snapshot, hareket, düşüş listesi, temizlik (+ api_odds_history.py)
app/scrapers/news.py   Google Haberler RSS toplayıcı
app/sentiment.py       TR/EN başlık duygu + sakatlık analizi
app/model/ratings.py   Elo, Poisson güçleri, form, puan durumu
app/model/predict.py   skor matrisi, pazarlar, oranlar
app/model/engine.py    tüm parametreleri birleştiren motor + geriye dönük test
app/main.py            FastAPI uç noktaları
app/telegram_bot.py    Telegram kanalına günlük kupon + sonuç paylaşımı
static/                web arayüzü
data/iddia.db          yerel SQLite veritabanı (DATABASE_URL yoksa; otomatik oluşur)
supabase/migrations/   Postgres şeması
scripts/               bir kerelik SQLite -> Postgres aktarımı
.github/workflows/     30 dk'lık tam güncelleme + saatlik Telegram paylaşımı (cron)
```

## Notlar

- Kaynak sitelerin HTML yapısı değişirse toplayıcı hata verebilir; hata arayüzde gösterilir.
- iddaa.com yalnızca o anda maç öncesi bülteninde yayımlanan oranları döndürür. Uzak tarihli veya henüz
  oran açılmamış ESPN fikstürlerinde iddaa oranı `-` görünür; Claude oranı gösterilmeye devam eder.
- Tahminler istatistiksel tahmindir, kesinlik içermez. Sorumlu oynayın.
