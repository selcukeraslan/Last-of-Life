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
(veya son güncelleme 6 saatten eskiyse) arka planda tam güncelleme başlar. İlk tam çekim 6 lig için birkaç
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
