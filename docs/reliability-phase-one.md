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
- CI hedefi Python 3.12 ve Node 22. İlk deneme aşağıdaki hesap engeline takıldı; public geçişinden sonra test yeniden başlatıldı.
- Üretim DB'sine veri yazılmadı; gerçek Telegram veya e-posta gönderilmedi.

## Ücretsiz GitHub Actions çalışması

GitHub check-run annotation'ı, işin son hesap ödemeleri başarısız olduğu veya harcama limitinin artırılması
gerektiği için başlamadığını bildiriyor. İncelenen iş: [hızlı güncelleme](https://github.com/selcukeraslan/Last-of-Life/actions/runs/39562776941).

Kullanıcının açık onayıyla repo 24 Ekim 2026'da **public** yapıldı. Standart GitHub-hosted runner'lar
public repolarda ücretsiz olduğundan bu işler için özel repo dakika kotasına bağlı kalınmaz.
Ödeme yöntemi veya harcama limiti değiştirilmedi. Bu, Supabase/Vercel gibi diğer servislerin ayrı kotalarını değiştirmez.

Geçiş öncesinde tüm uzak dallar, Git geçmişi, issue/PR içerikleri ve yorumlar incelendi.
Gitleaks 8.30.1 Git geçmişi ve yorum taramalarında gizli anahtar bulmadı; ek bağlantı şifresi/dosya taraması da temizdi.
Bu kontroller, tüm olası hassas içeriğin bulunacağını garanti etmez.

Yalnız Tests işi yeniden çalıştırıldı. Veri güncelleme ve gerçek Telegram paylaşımı elle tetiklenmedi.

## Kalan işler

İnceleme raporunun ikinci/üçüncü grupları: sahiplik token'lı güncelleme kilidi, kalıcı backtest işi,
zamana bağlı önbellek TTL'i, küçük lig filtreleri, canlı skor süre bütçesi, migration sürüm çakışması,
bağımlılık kilidi ve ileriye dönük model doğrulaması.

Eski desteklenmeyen kupon pazarları için geçmiş veri otomatik değiştirilmez; elle doğrulama uyarısı gösterilir.
Önceden gönderilmiş Telegram mesajlarının eski payload'ı da geriye dönük yeniden yazılmaz.
