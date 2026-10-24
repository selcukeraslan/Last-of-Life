# Öneri mantığı ve yapılan düzeltmeler

## Hesap nasıl çalışıyor?

Takımların geçmiş maçları zaman ağırlığıyla değerlendirilir (yarı ömür 200 gün); az veride lig ortalamasına yaklaşılır. Hücum/savunma gücü ve Elo, beklenen golleri oluşturur. Son form, dinlenme ve ilgili haberlerin etkisi eklenir. Dixon–Coles düzeltmeli Poisson skor dağılımından pazar olasılıkları çıkarılır. Tam ve geçerli iddaa oran grupları varsa marjı temizlenerek modelle %50 harmanlanır. Eksik gruplar model olasılığında kalır.

Güven etiketi olasılık ve takımların geçmiş maç miktarından hesaplanan bir göstergedir; “Yüksek güven” ölçülmüş kazanma yüzdesi demek değildir. Haber olmaması “eksik oyuncu yok” diye yorumlanmaz ve tek başına güveni düşürmez. Daha önce haber bulunmamasına otomatik “Düşük” kısıtı uygulanıyordu; haber verisi yokken bütün maçları gereksiz yere aşağı çekebildiği için kaldırıldı.

## İsabet öncelikli seçim (`hit_rate_v1`)

- Eski 1,40 alt sınırı, yüksek olasılıklı düşük oranlı seçimleri eliyordu. Varsayılan alt sınır 1,01 oldu.
- Maç sonucu, çifte şans, 1,5/2,5/3,5 alt–üst ve KG pazarları arasından en yüksek tahmini olasılık seçilir. İlk yarı ve kesin skor önerilmez.
- Gerçek oran verisi varsa yalnız geçerli gerçek oranı bulunan pazarlar seçilebilir. Gerçek oran seçim için kullanılır; modelin ürettiği tahmini oran gerçek fiyat gibi kabul edilmez.
- Oran hiç yoksa model önerisi ayrı kaynakla işaretlenir. Oran listesi var ama geçerli seçenek yoksa öneri verilmez. NaN, sonsuz ve geçersiz olasılık/oranlar elenir.
- Eksik oran grubunda bile mevcut tekil gerçek oranlar seçime katılır; tam grup gereksinimi yalnız piyasa olasılığı harmanlaması içindir.

Bu tercih tek maçta tutma ihtimalini önceler; kârlılık veya yüksek kupon getirisi hedefi değildir. Birçok düşük oranı birleştirmek toplam tutma ihtimalini düşürür. Banko ve sürpriz otomatik kuponların farklı amaçları olan kuralları korunur.

## Gerçek başarı nasıl ölçülüyor?

İlk yayımlanan maç öncesi öneri, olasılık, güven etiketi, model sürümü ve seçim yöntemi değişmez kaydedilir. Biten maçlarda o günkü önerinin sonucu hesaplanır; sonraki öneriyle değiştirilmez. Karne tablosunda lig/güven/sürüm bazında tutan/toplam, gerçekleşen isabet, ortalama tahmini olasılık ve yaklaşık %95 Wilson aralığı gösterilir. Az örneklem geniş aralık verir. Güven etiketi kaydedilmemiş eski maçlar geriye dönük tahminle doldurulmaz. Maç başladıktan sonra alınan kayıtlar değerlendirmeye girmez.

Elo, haber ve piyasa ağırlıkları bu değişiklikte optimize edilmiş gibi sunulmadı: yeni seçim yönteminin başarısını gösterecek ileriye dönük sonuçlar henüz birikmedi. Yeni yöntemin daha başarılı olduğu veya matematiksel olarak en iyi ayar olduğu iddia edilmez. Ağırlık değişikliği için yeterli maç öncesi kayıt ve zamana göre ayrılmış değerlendirme gerekir.

Aralık hesabı: [NIST — Wilson yöntemi](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm). Maçlar arasındaki bağımlılık bu yaklaşık aralıkta modellenmez.
