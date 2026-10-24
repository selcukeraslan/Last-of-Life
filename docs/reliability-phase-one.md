# Güvenilirlik düzeltmeleri — ilk aşama

24 Ekim 2026 tarihli repo incelemesinin ilk grubundaki kod düzeltmeleri.

## Tamamlananlar

- Lig, iddaa ve haber için son deneme, son başarı ve hata durumu ortak DB metadata'sında tutulur.
- Kısmi/başarısız güncelleme genel başarı zamanını ilerletmez. Kısmi veri değişimi yine model önbelleğini geçersiz kılar.
- Toplayıcılardaki ağ/pencere hataları güncelleme katmanına aktarılır; başarılı boş yanıt hata sayılmaz.
- Otomatik kuponlar yalnız sonuçlandırılabilen tam maç pazarlarını seçer. Geçmiş ve Telegram ortak sonuç/iptal kurallarını kullanır.
- Günün yayımlanan Banko/Sürpriz kuponları web, geçmiş ve Telegram'da aynı kayıttır. Güncel alternatifler ayrı etiketlenir.
- PWA kullanıcı/auth ve private/no-store yanıtlarını saklamaz. Eski API önbelleği silinir; oturum değişiminde API önbelleği temizlenir.
- Giriş zorunlu kurulumlarda API ve ana sayfa oturum kontrolü çevrimdışı önbellekten karşılanmaz.
- Push/PR test CI'ı eklendi. Yeni DB migration'ı gerekmez; mevcut kupon tabloları ve meta kullanılır.

## Doğrulama

- Yerel Python 3.14: 257 unittest testi geçti. Bazı testler Node testlerini de çağırır.
- Yerel Node 24: 39 JS testi geçti; sayı Python test sayısıyla benzersiz test olarak toplanmamalı.
- Yeni senaryolar: tüm kaynakların çökmesi, kısmi güncelleme, başarısız kaynağın son başarı zamanını koruma,
  boş kaynak yanıtı, resume checkpoint'i, desteklenmeyen otomatik pazarlar, ortak kupon kaydı,
  ortak sonuçlandırma ve PWA gizlilik/çevrimdışı davranışı.
- CI hedefi Python 3.12 ve Node 22; uzak doğrulama aşağıdaki hesap engeli nedeniyle bekliyor.
- Üretim DB'sine veri yazılmadı; gerçek Telegram veya e-posta gönderilmedi.

## Hesap sahibinin çözmesi gereken engel

GitHub check-run annotation'ı, işin son hesap ödemeleri başarısız olduğu veya harcama limitinin artırılması
gerektiği için başlamadığını bildiriyor. İncelenen iş: [hızlı güncelleme](https://github.com/selcukeraslan/Last-of-Life/actions/runs/39562776941).

GitHub **Settings → Billing & plans** kontrol edilmeli. Bu bir workflow kod hatası değil; hesap engeli
giderildikten sonra Tests, hızlı güncelleme ve tam güncelleme doğrulanmalı. Telegram işi gerçek paylaşım
yaptığından tekrar çalıştırılması kanal davranışı dikkate alınarak yapılmalı.

## Kalan işler

İnceleme raporunun ikinci/üçüncü grupları: sahiplik token'lı güncelleme kilidi, kalıcı backtest işi,
zamana bağlı önbellek TTL'i, küçük lig filtreleri, canlı skor süre bütçesi, migration sürüm çakışması,
bağımlılık kilidi ve ileriye dönük model doğrulaması.

Eski desteklenmeyen kupon pazarları için geçmiş veri otomatik değiştirilmez; elle doğrulama uyarısı gösterilir.
Önceden gönderilmiş Telegram mesajlarının eski payload'ı da geriye dönük yeniden yazılmaz.
