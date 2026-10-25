# Günlük bülten, oranlar ve öneri mantığı

Ana ekran Türkiye gününe göre bütün ana ligleri tek bültende gösterir: Süper Lig, Premier League, La Liga, Bundesliga, Serie A ve diğer ana ligler. Gün seçimi bugün/yarın/ertesi gün veya takvimle yapılır. Ana lig filtresi korunur. Diğer ligler tek günlük bülten olarak açılır; tek tek lig seçilmez. Model eşleşmesi olmayan iddaa etkinlikleri de gerçek oranlarıyla görünür, model verisi varmış gibi sunulmaz.

## Gerçek oranlar

İddaa'nın maç öncesi events yanıtı yalnız özet pazarları içerir. Güncelleme tam maç detayını da alır; güncel bültendeki daha yeni fiyat eski detayla değişmez. Detay çekimi hızlı güncelleme bütçesi içinde 6 paralel bağlantı, 6 saniye istek süresi, toplam 20 saniye ve en çok 400 maçla sınırlıdır. Ana ligler ve yakın maçlar önce işlenir. Başarısız detayda geçerli özet oranlar korunur. Kaç detayın alınabildiği bülten üst bilgisinde görünür; tüm pazarların her zaman eksiksiz alınmış olduğu iddia edilmez.

Site `odd` alanını gösterir; `wodd` üzeri çizili önceki orandır. Uygulama `odd` kullanır. Kapalı, geçersiz ve sonsuz oranlar elenir. Boş veya artımlı yanıt tam bültenmiş gibi kabul edilip kayıtlar silinmez. Öneriler yalnız gerçek oran varsa yayımlanır; modelin ürettiği fiyat gerçek iddaa oranı gibi kullanılmaz. Kupona elle eklenmiş eski tahmini fiyatlar ayrı etiketlenir.

ÇŞ 1–2, ev sahibi veya deplasman galibiyetidir; beraberlikte kaybeder. Önceki “MS12” etiketi hatalıydı. [İddaa'nın açıklaması](https://www.iddaa.com/yardim/futbol/detay/cifte-sans-259).

## Model ve güven

Takım hücum/savunma gücü, zaman ağırlıklı geçmiş maçlar, Elo, form, dinlenme ve ilgili haberlerden beklenen gol sayıları hesaplanır. Dixon–Coles düzeltmeli Poisson dağılımından pazar olasılıkları çıkarılır. Tam ve geçerli gerçek oran grubu varsa marjı temizlenerek modelle %50 harmanlanır. Ağırlıklar yeni sonuçlar olmadan değiştirilmiş gibi gösterilmez.

Güven etiketi tahmini olasılık ve iki takımdan daha az geçmişi olanın zaman ağırlıklı maç sayısından hesaplanır. %62 ve üstü olasılık yüksek etikete adaydır; veri 12 maçın altındaysa en fazla orta, 8'in altındaysa düşük olur. Haber bulunmaması tek başına güveni düşürmez. “Yüksek güven” ölçülmüş kazanma yüzdesi değildir.

## Dengeli öneri (`balanced_v2`)

Tek maçta 1,40–2,30 gerçek oran bandından, tahmini olasılığı en az %56 olan en olası seçenek seçilir. 1,05 gibi düşük fiyat bütün önerileri bastırmaz; bandın dışına çıkıp zorla öneri üretilmez. Bu bant kullanıcının “ortalama oran ve yüksek güven” tercihini ifade eder; kazanç veya başarı garantisi değildir.

Dengeli (Banko) kupon: gerçek oran 1,40–2,30, seçim olasılığı en az %62, en az 8 ağırlıklı maç verisi, 2–3 farklı maç, toplam oran 1,90–8 ve ortak tahmini olasılık en az %25. Sürpriz: gerçek oran 1,80–3,50, olasılık %38–70, 3–4 farklı maç, toplam oran 8–25 ve ortak tahmini olasılık en az %4. Kaynağın MBS (asgari farklı maç sayısı) şartı da sağlanır. Uygun aday yoksa kupon oluşturulmaz.

Önce veri güveninin en düşük olduğu seçim kademesi, ardından ortak tahmini olasılık değerlendirilir. En fazla 14 maçlık havuzda maç başına iki pazar alternatifi denenir; her maç yalnız bir kez kullanılır. Ek maç ancak gerekli olduğunda eklenir. Sürpriz kupon yalnız beraberlik/deplasman pazarlarına zorlanmaz. Bunlar ürün seçim kurallarıdır; geriye dönük ölçümle kanıtlanmış en kârlı parametreler olarak sunulmaz.

Günün güncel alternatifleri ve önceki yayımlanmış kuponu ayrıdır. Tarih/Telegram kayıtları sonradan değişmez; yeni kurallar güncel alternatiflere hemen yansır.

## Deneysel seçimler

İlk yarı, İY/MS ve handikap olasılıkları deneysel olarak hesaplanır. Gerçek fiyatı bulunan deneysel pazarlar maç detayından Kuponum'a eklenebilir. Korner/kart oranı da eklenebilir; geçmiş veri olmadığı için bu seçimlere olasılık uydurulmaz ve toplam kupon şansı gösterilmez.

Kaynakta negatif handikap 0:|çizgi| olarak gösterilir (deplasman avantajı); hesapta imzalı çizgi ev sahibi skoruna eklenir. Tam skor handikabı sonuçlandırabilir. İlk yarı/İY-MS/korner/kart sonucu tam maç skorundan çıkarılamaz; maç bittikten sonra kullanıcı tarafından doğrulanır ve bu durum işaretlenir. Deneysel pazarlar otomatik Banko/Sürpriz'e alınmaz.

## Gerçek başarı ölçümü

İlk yayımlanan maç öncesi öneri, olasılık, güven etiketi, model sürümü ve yöntem değişmez kaydedilir. Lig/güven/sürüm/yöntem bazında tutan/toplam ve ortalama tahmini olasılık gösterilir. Eski kayıtlara sonradan güven etiketi atanmaz. Maç başladıktan sonra kaydedilen tahmin ölçüme girmez. Yaklaşık %95 Wilson aralığı az örneklemde belirsizliği gösterir; maçlar arası bağımlılık bu yaklaşık aralıkta modellenmez. [NIST yöntemi](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).
