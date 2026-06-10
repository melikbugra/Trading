// Buy/sell decision flows for long-term investing. Rendered inside FlowPanel
// (side window next to a stock's report). One flow at a time via the `flow` prop.

const BUY_STEPS = [
  {
    id: 'aday',
    icon: '🎯',
    title: '1. Aday Belirle',
    subtitle: 'İncelemeye bir hisse seç',
    color: 'blue',
    what: 'İncelemeye bir hisse seçerek başla. Bu adımların sonunda "alayım mı, almayayım mı" diye karar vereceksin.',
    look: 'Tarayıcıda puanı yüksek çıkanlar, izleme listendekiler veya bir haberde gördüğün şirket iyi bir başlangıç olabilir.',
    where: '"Analiz & Tarayıcı" veya "İzleme" sekmesi.',
    tip: 'Ne iş yaptığını bilmediğin şirketi alma. Anlamadığın işe para koyma.',
  },
  {
    id: 'kalite',
    icon: '🏗️',
    title: '2. Temel Kalite',
    subtitle: 'Şirket iyi bir şirket mi?',
    color: 'green',
    what: 'Önce şirketin sağlam ve kâr eden bir şirket olup olmadığına bak. Kötü bir şirketi, ne kadar ucuz olursa olsun, almak istemezsin.',
    look: 'Aşağıdaki oranlara bak. Her birinin ne olduğu ve hangi değerin iyi/kötü sayıldığı yanında yazıyor. Çoğu iyi tarafta ise şirket kalitelidir.',
    terms: [
      { t: 'ROE (Özkaynak Kârlılığı)', d: 'Şirket, ortakların koyduğu parayla yılda yüzde kaç kâr ediyor. Yüksek olması iyidir. Kabaca: %10 altı zayıf, %15–20 iyi, %20 üstü çok iyi.' },
      { t: 'Net Kâr Marjı', d: 'Şirket 100 TL’lik satıştan kaç TL net kâr bırakıyor. %10 üstü iyi, %20 üstü çok iyi. Eksi (negatif) ise şirket zarar ediyor demektir.' },
      { t: 'Borç / Özkaynak', d: 'Şirketin borcunun, kendi sermayesine oranı. Düşük olması daha sağlam demektir. 1,0 (%100) altı rahat, 2,0 (%200) üstü yüksek borç (riskli). Bankalarda bu sayı anlamsızdır, boş görebilirsin.' },
      { t: 'Gelir / Kâr Büyümesi', d: 'Satışların ve kârın geçen yıla göre yüzde kaç arttığı. Pozitif ve istikrarlı olması iyidir; %15 üstü güçlü büyümedir.' },
    ],
    where: 'Rapor → Temettü Skoru & Büyüme Skoru ve "Temel Oranlar" tablosu.',
    tip: 'Uygulama bu oranları senin için 0–100 puana çeviriyor (Temettü ve Büyüme skoru). Düşük puanlı şirket genelde burada elenir.',
    branch: 'Kalite zayıfsa → GEÇ',
    branchNote: 'Bu adımı geçemezse hisseyi alma listesinden çıkar.',
  },
  {
    id: 'deger',
    icon: '🏷️',
    title: '3. Değerleme',
    subtitle: 'Fiyatı pahalı mı, ucuz mu?',
    color: 'cyan',
    what: 'Şirket iyi olabilir ama fiyatı çok yüksekse yine kötü bir alım olur. Amaç: iyi şirketi makul fiyata almak.',
    look: 'Fiyatın pahalı mı ucuz mu olduğunu aşağıdaki iki orana bakarak anlarsın. Mutlaka aynı sektördeki benzer şirketlerle kıyasla.',
    terms: [
      { t: 'F/K = Fiyat / Kazanç (İng. P/E)', d: 'Hisse fiyatının, şirketin hisse başına yıllık kârına oranı. Kısaca: "Şirketin 1 yıllık kârının kaç katı parayla bu hisseyi alıyorum." Düşük = ucuz. Kabaca: 10 altı ucuz, 10–20 normal, 25 üstü pahalı. (Bankalarda normalde düşüktür, teknolojide yüksektir — o yüzden sektörle kıyasla.)' },
      { t: 'F/DD = Fiyat / Defter Değeri (İng. P/B)', d: 'Hisse fiyatının, şirketin defter değerine oranı. Defter değeri = şirketin varlıkları eksi borçları (muhasebedeki net değeri). Kısaca: "Şirketin net varlığının kaç katını ödüyorum." 1 altı = net değerinin altında (ucuz olabilir), 1–3 normal, 3 üstü pahalı/primli.' },
    ],
    where: 'Rapor → Değer Skoru (sektöre göre ucuzluğu 0–100 puana çevirir; 100 = sektörünün en ucuzu).',
    tip: 'Bir hisse çok ucuz görünüyorsa "neden?" diye sor. Bazen şirketin başı dertte olduğu için ucuzdur — buna "değer tuzağı" denir.',
  },
  {
    id: 'haber',
    icon: '📰',
    title: '4. İş Modeli & Haberler',
    subtitle: 'Şirketi anla, gelişmelere bak',
    color: 'purple',
    what: 'Şirketin parayı nasıl kazandığını anla ve son gelişmelere bak. Rakamlar iyi olsa bile kötü bir haber her şeyi değiştirebilir.',
    look: 'Şirket ne iş yapıyor? Bilanço (mali tablo) ne zaman açıklanacak? Son haberlerde kötü bir gelişme var mı?',
    terms: [
      { t: 'Bilanço', d: 'Şirketin belirli aralıklarla (genelde 3 ayda bir) açıkladığı mali tablo: ne kadar satış yaptı, ne kadar kâr/zarar etti, borcu ne. Yatırımcılar bunu yakından izler.' },
      { t: 'Özel Durum Açıklaması', d: 'Şirketin yatırımcıyı etkileyebilecek önemli bir gelişmeyi (yeni yatırım, dava, satış, temettü kararı vb.) resmî olarak duyurması.' },
    ],
    where: 'Rapor → Haberler sekmesi; ayrıca üstteki "Haberler" sekmesi.',
    tip: 'Bilanço açıklanmasına çok az kala büyük alım yapma; sonuç sürpriz çıkarsa fiyat sert oynayabilir.',
  },
  {
    id: 'teknik',
    icon: '📈',
    title: '5. Teknik Analiz — Son Kontrol',
    subtitle: 'Almadan önce grafiğe bak',
    color: 'cyan',
    what: 'Almaya karar vermeden hemen önce fiyatın grafiğine bak: şu an sert bir tepede (pahalı) mi, yoksa makul bir seviyede mi? Bu adım "hangi hisse" sorusunu değil, "ne zaman / hangi fiyattan" sorusunu yanıtlar.',
    look: 'Fiyat 200 günlük ortalamanın üstünde mi (yükseliş trendi)? RSI aşırı alımda mı (pahalı, geri çekilebilir)? Son yükseliş çok mu sert? Teknik skor ne diyor?',
    terms: [
      { t: 'EMA200 (200 Günlük Ortalama)', d: 'Son 200 günün ortalama fiyatı. Fiyat bu çizginin ÜSTÜndeyse uzun vadeli yükseliş trendi, ALTındaysa düşüş trendi kabul edilir. En çok izlenen uzun vade trend göstergesidir.' },
      { t: 'RSI (Göreceli Güç Endeksi)', d: '0–100 arası momentum göstergesi. 70 üstü "aşırı alım" = fiyat hızlı yükselmiş, pahalı/geri çekilebilir. 30 altı "aşırı satım" = fiyat hızlı düşmüş, ucuz/tepki gelebilir. 40–60 arası nötr.' },
      { t: 'Teknik Skor — kaçta al?', d: '0–100 arası giriş uygunluğu. 60 ve üstü: trend yukarı, giriş için uygun (yeşil ışık). 40–60: nötr, acele etme, kademeli al. 40 altı: trend zayıf/aşağı, ideal an değil — temel güçlüyse yine de küçük ve kademeli girebilirsin.' },
      { t: 'Destek / Direnç', d: 'Destek = fiyatın geçmişte düşüşten döndüğü seviye; direnç = yükselişin takıldığı seviye. Desteğe yakın almak, dirence yakın almaktan daha avantajlıdır.' },
      { t: 'Geri çekilme (drawdown)', d: 'Fiyatın son 1 yılın zirvesinden yüzde kaç aşağıda olduğu. Kaliteli bir hisseyi zirveden makul bir geri çekilmeyle almak daha iyi giriş sağlar.' },
    ],
    where: 'Rapor → "📈 Teknik Analiz" butonu (grafik + EMA50/EMA200 + RSI + destek/direnç + skor + okuma).',
    tip: 'Kural: teknik skor 60+ ise giriş elverişli; 40 altıysa temel güçlü olsa bile küçük ve kademeli başla. Uzun vadede teknik analiz şart değildir, sadece giriş fiyatını iyileştirir.',
  },
  {
    id: 'karar',
    icon: '⚖️',
    title: '6. Karar: Al / İzle / Geç',
    subtitle: 'Bilgiyi birleştir, karar ver',
    color: 'yellow',
    what: 'Topladığın bilgiyi birleştirip karar ver. Uygulama sana puan ve uyarı verir, ama son kararı sen verirsin.',
    look: 'Basit kural: Kalite yüksek + fiyat makul + şirketi anlıyorsun → AL. Şirket iyi ama pahalı → İZLE (ucuzlamasını bekle). Kalite zayıf → GEÇ.',
    where: 'Burada karar veren sensin; uygulama sadece yol gösterir.',
    tip: 'Kararsızsan alma, izlemeye al. Bir fırsatı kaçırmak, yanlış hisseye para koymaktan daha iyidir.',
  },
  {
    id: 'boyut',
    icon: '🧩',
    title: '7. Pozisyon & Çeşitlendirme',
    subtitle: 'Ne kadar alınmalı?',
    color: 'pink',
    what: 'Almaya karar verdiysen, ne kadar alacağına karar ver. Paranın hepsini tek hisseye koyma.',
    look: 'Genel kabul gören kabaca kurallar aşağıda. Bunlar kesin kural değil, koruyucu sınırlardır.',
    terms: [
      { t: 'Tek hisse sınırı', d: 'Bir hisse, portföyünün dörtte birinden (%25) fazlası olmasın. O hisse batarsa zarar sınırlı kalsın diye.' },
      { t: 'Sektör sınırı', d: 'Aynı sektöre (ör. hepsi banka) portföyünün %40’ından fazlasını yığma. Sektör topluca düşerse korunmuş olursun.' },
      { t: 'Para birimi dengesi', d: '₺ ve $ varlıklar arasında denge tut. TL değer kaybederse $ hisseler dengeler (doğal koruma).' },
      { t: 'Çeşitlendirme', d: 'Parayı farklı hisse ve sektörlere yaymak. Tek bir şirkete bağlı kalmamak riski azaltır.' },
    ],
    where: 'Portföy → "Risk & Dağılım" kartı bunları senin için hesaplar ve sınır aşılırsa uyarır.',
    tip: 'En güvendiğin hisse bile portföyünün küçük bir kısmı olmalı. Dağılım, tek hisse seçmekten daha çok korur.',
  },
  {
    id: 'kademe',
    icon: '📉',
    title: '8. Kademeli Alım',
    subtitle: 'Tek seferde değil, parça parça al',
    color: 'green',
    what: 'Parayı tek seferde değil, birkaç parçaya bölüp farklı zamanlarda al.',
    look: 'Örneğin almak istediğin miktarı 2–3 parçaya böl, farklı gün/fiyatlarda al. Böylece "yanlış günde hepsini aldım" riskini azaltırsın.',
    terms: [
      { t: 'Kademeli alım (DCA)', d: 'İngilizcesi "Dollar Cost Averaging". Sabit bir tutarı zamana yayarak almak. Bazen ucuza bazen pahalıya alırsın, ortalama bir maliyetin olur — zamanlama stresini azaltır.' },
    ],
    where: 'Alımı Midas’tan elle yaparsın. Daha iyi giriş zamanı istersen "Gün İçi Trade" uygulamasındaki teknik analizden yararlanabilirsin.',
    tip: 'Kademeli aldığın için uzun vadede tek tek "en doğru günü yakalama" (teknik analiz) şart değildir.',
  },
  {
    id: 'takip',
    icon: '🔁',
    title: '9. Takip & Gözden Geçir',
    subtitle: 'Aldıktan sonra izlemeyi sürdür',
    color: 'blue',
    what: 'Hisseyi aldıktan sonra ara sıra kontrol et. Şirketin durumu bozulduysa çıkmayı bil (→ Satma Akışı).',
    look: 'Yeni bilanço nasıl geldi? Temel skorlar düştü mü? Kötü haber veya temettü kesintisi var mı?',
    where: 'Portföy + Haberler + ara ara yeniden tarama.',
    tip: 'Sadece fiyat düştü diye satma. "Bu hisseyi neden almıştım?" sebebin hâlâ geçerliyse tut; sebep çürüdüyse sat.',
  },
];

const SELL_STEPS = [
  {
    id: 'dur',
    icon: '🛑',
    title: '1. Önce Dur — Duyguyla Satma',
    subtitle: 'Sebep gerçek mi, panik mi?',
    color: 'yellow',
    what: 'Satış kararını korku veya heyecanla değil, somut bir sebeple ver. Uzun vadeli yatırımda en sık ve en pahalı hata, sadece fiyat düştü diye panikle satmaktır.',
    look: 'Kendine sor: "Satmak istememin gerçek sebebi ne? Şirkette kötü bir şey mi oldu, yoksa sadece fiyat mı düştü / haberler mi korkuttu?"',
    where: 'Bu adım kafanda; aşağıdaki adımlar sebebini netleştirir.',
    tip: 'Sadece fiyatın düşmesi satış sebebi DEĞİLDİR. İyi şirketler de zaman zaman ucuzlar — çoğu zaman o an satılacak değil eklenecek andır.',
  },
  {
    id: 'tez',
    icon: '🧩',
    title: '2. Tez Hâlâ Geçerli mi?',
    subtitle: 'Aldığın sebep duruyor mu?',
    color: 'blue',
    what: 'Bu hisseyi neden almıştın? (kâr ediyor, büyüyor, temettü veriyor, sektöründe güçlü…) O sebepler hâlâ geçerli mi? "Tez" = bir hisseyi almanın arkasındaki gerekçe.',
    look: 'Alma gerekçen bozulmadıysa, fiyat ne yaparsa yapsın genelde TUTMAK doğrudur.',
    where: 'Rapor → Temel skorlar & Haberler ile gerekçeni tekrar kontrol et.',
    tip: '"Bu şirketi neden aldım?" sorusunun cevabı hâlâ evetse, geçici fiyat düşüşleri seni satışa zorlamamalı.',
    branch: 'Tez sağlamsa → TUT',
    branchNote: 'Alma gerekçen hâlâ geçerliyse satma; tutmaya devam et.',
  },
  {
    id: 'temel-bozulma',
    icon: '📉',
    title: '3. Temeller Bozuldu mu?',
    subtitle: 'Şirket kalıcı olarak kötüleşti mi?',
    color: 'pink',
    what: 'Satışın en sağlam sebebi: şirketin temelleri kalıcı olarak kötüleşti. Geçici bir kötü çeyrek değil, yapısal bir bozulma.',
    look: 'Aşağıdaki somut işaretlerden biri/birkaçı kalıcıysa, satış güçlü bir seçenektir.',
    terms: [
      { t: 'Temettü kesintisi / iptali', d: 'Düzenli temettü veren bir şirketin temettüyü azaltması veya kesmesi — genelde işlerin kötüye gittiğinin ilk habercisidir.' },
      { t: 'Sürekli kâr düşüşü', d: 'Tek bir kötü çeyrek değil; üst üste birkaç dönem kâr/satış düşüşü ve toparlanma işaretinin olmaması.' },
      { t: 'Artan borç', d: 'Borç/özkaynağın hızla yükselmesi, faiz ödemelerinin kârı eritmeye başlaması.' },
      { t: 'Rekabet / pazar kaybı', d: 'Rakiplerin öne geçmesi, ürünün/işin demode olması, pazar payının erimesi.' },
    ],
    where: 'Rapor → Temel Oranlar, finansal tablolar ve Haberler.',
    tip: 'Bir kötü çeyrek tek başına satış sebebi değildir. Kalıcı ve birikmiş bir bozulma ara.',
    branch: 'Temeller bozulduysa → SAT',
    branchNote: 'Temeller kalıcı olarak bozulduysa, zararına bile olsa çıkmayı ciddi düşün — daha çok kaybetmeden.',
  },
  {
    id: 'asiri-pahali',
    icon: '🏷️',
    title: '4. Aşırı Pahalı mı?',
    subtitle: 'Fiyat değerinin çok mu önüne geçti?',
    color: 'cyan',
    what: 'Şirket iyi olsa bile fiyatı, gerçek değerinin çok üstüne çıktıysa bir kısmını satıp kârı realize etmek mantıklı olabilir.',
    look: 'F/K, hissenin tarihsel ortalamasının ve sektörün çok mu üstünde? Fiyat kısa sürede aşırı mı yükseldi (RSI çok yüksek)?',
    terms: [
      { t: 'Aşırı değerleme', d: 'Fiyatın, şirketin kazanç ve büyümesinin haklı çıkardığından çok yukarıda olması.' },
      { t: 'Kâr realizasyonu (kâr al)', d: 'Kazancın bir kısmını satıp nakde çevirmek. Genelde tamamı değil, bir kısmı satılır (buna "trim" / azaltma denir).' },
      { t: 'Teknik Skor — kaçta sat?', d: 'Teknik skor TEK BAŞINA satış sebebi değildir (uzun vadede satışı temeller belirler). Destekleyici işaret olarak: (1) Skor 30 ALTINA düşer ve fiyat 200 günlük ortalamanın altına geçerse trend aşağı dönmüştür — temeller de zayıflıyorsa çıkışı güçlendirir. (2) RSI 75 ÜSTÜ + çok yüksek skor + aşırı pahalıysa, kısa vadeli aşırı ısınma demektir; bir kısmını satıp (trim) kâr realize etmek için uygun an.' },
    ],
    where: 'Rapor → Değer Skoru + "📈 Teknik Analiz" (RSI / aşırı alım / teknik skor).',
    tip: 'Aşırı pahalılıkta genelde hepsini değil bir kısmını sat. Yükseliş sürerse tamamen dışarıda kalmazsın.',
  },
  {
    id: 'denge',
    icon: '🧮',
    title: '5. Portföyde Çok mu Büyüdü?',
    subtitle: 'Tek hisse/sektör çok mu ağır bastı?',
    color: 'purple',
    what: 'Bir hisse çok kazandırıp portföyünün çok büyük bir kısmı hâline geldiyse, riski azaltmak için bir kısmını satmak (dengeleme) iyi fikirdir.',
    look: 'Tek hisse portföyünün %25’ini, tek sektör %40’ını aştı mı?',
    terms: [
      { t: 'Yeniden dengeleme (rebalancing)', d: 'Aşırı büyüyen bir pozisyonun bir kısmını satıp portföyü hedef dağılıma geri getirmek. Şirket kötü olduğu için değil, denge için yapılır.' },
    ],
    where: 'Portföy → "Risk & Dağılım" kartı (sınır aşılırsa uyarır).',
    tip: 'Bu satış, şirket kötü diye değil, "yumurtaları tek sepete koymamak" için yapılır. Yalnızca fazlasını sat.',
  },
  {
    id: 'firsat',
    icon: '🔄',
    title: '6. Daha İyi Fırsat / İhtiyaç',
    subtitle: 'Para başka yerde daha mı iyi?',
    color: 'green',
    what: 'Parana belirgin biçimde daha iyi bir yer bulduysan ya da paraya ihtiyacın olduysa / hedefe ulaştıysan satmak mantıklıdır.',
    look: 'Eldeki hisse vs. yeni fırsat: yenisi gerçekten daha mı iyi (daha kaliteli + daha ucuz)? Yoksa sadece heyecan mı?',
    where: 'Tarayıcı ile alternatifleri kıyasla.',
    tip: 'İyi bir hisseyi sadece "şu daha çok yükselir" tahminiyle satma. Elindeki kötüleşmediyse acele etme.',
  },
  {
    id: 'satis-karar',
    icon: '⚖️',
    title: '7. Karar: Tut / Kısmi Sat / Hepsini Sat',
    subtitle: 'Sebepleri birleştir',
    color: 'yellow',
    what: 'Yukarıdaki adımları birleştirip karar ver.',
    look: 'Net kural: Tez bozuldu → genelde HEPSİNİ SAT. Sağlam ama aşırı pahalı / çok büyümüş → KISMİ SAT. Geçerli sebep yok, sadece korku → TUT.',
    where: 'Karar senin; uygulama sadece veriyi gösterir.',
    tip: 'Kararsızsan, hepsini değil bir kısmını satmak çoğu zaman duygusal baskıyı azaltan dengeli bir yoldur.',
  },
  {
    id: 'kademeli-sat',
    icon: '📤',
    title: '8. Kademeli Sat',
    subtitle: 'Tek seferde değil, parça parça',
    color: 'cyan',
    what: 'Özellikle pahalılık veya dengeleme satışında, tek seferde değil parçalar halinde sat. Böylece "tam dipte sattım" riskini azaltırsın.',
    look: 'Satışı 2–3 parçaya böl. (Tez tamamen bozulduysa bu kural gevşer — orada hızlı ve net çıkmak daha önemli olabilir.)',
    terms: [
      { t: 'İşlem ücreti', d: 'BIST’te Midas komisyonsuz; ABD hisselerinde emir başına ~$1,5. Çok küçük parçalara bölersen ABD’de komisyon birikebilir, ona göre böl.' },
    ],
    where: 'Satışı Midas’tan elle yaparsın.',
    tip: 'Tez bozulması = hızlı ve net çık. Pahalılık / dengeleme = sabırlı ve kademeli çık.',
  },
  {
    id: 'sat-kayit',
    icon: '🧾',
    title: '9. Sat ve Kaydı Güncelle',
    subtitle: 'Portföyü güncelle, dersini al',
    color: 'blue',
    what: 'Sattıktan sonra portföy kaydını güncelle ve neden sattığını kısa bir not olarak yaz — gelecekte aynı dersi tekrar öğrenmemek için.',
    look: 'Tamamını sattıysan portföyden çıkar; bir kısmını sattıysan adedi güncelle.',
    where: 'Portföy → ilgili pozisyonu Sil veya düzenle.',
    tip: 'Sattığın hisseyi izleme listene alabilirsin; tez tekrar düzelir ve fiyat uygunsa ileride geri girebilirsin.',
  },
];

export const FLOW_META = {
  buy: { label: '📥 Alma Akışı', steps: BUY_STEPS, branchDefault: 'Bu adımı geçemezse hisseyi alma.' },
  sell: {
    label: '📤 Satma Akışı',
    steps: SELL_STEPS,
    branchDefault: 'Bu adım sağlandıysa ilgili kararı uygula.',
    caution: 'Uzun vadeli satış FİYATLA değil, ŞİRKETİN DURUMUYLA olur. Gün içi trade’deki gibi sıkı "stop-loss" (fiyat düşünce otomatik sat) burada kullanılmaz — kararı temeller belirler.',
  },
};

const COLOR = {
  blue: 'border-blue-500/50 hover:border-blue-400 text-blue-300',
  green: 'border-green-500/50 hover:border-green-400 text-green-300',
  cyan: 'border-cyan-500/50 hover:border-cyan-400 text-cyan-300',
  purple: 'border-purple-500/50 hover:border-purple-400 text-purple-300',
  yellow: 'border-yellow-500/50 hover:border-yellow-400 text-yellow-300',
  pink: 'border-pink-500/50 hover:border-pink-400 text-pink-300',
};

function DetailRow({ label, children }) {
  return (
    <div className="flex gap-2 text-sm">
      <span className="text-gray-500 shrink-0 w-20">{label}</span>
      <span className="text-gray-300">{children}</span>
    </div>
  );
}

// Renders one flow's steps as a clickable accordion. `openId`/`setOpenId` are
// owned by the parent so the open step persists across re-renders.
export default function FlowSteps({ flow, openId, setOpenId }) {
  const cfg = FLOW_META[flow];
  if (!cfg) return null;
  const steps = cfg.steps;

  return (
    <div>
      {cfg.caution && (
        <div className="text-xs text-yellow-300 bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-2.5 mb-3">
          ⚠️ {cfg.caution}
        </div>
      )}

      <div className="flex flex-col items-stretch">
        {steps.map((s, i) => {
          const open = openId === s.id;
          return (
            <div key={s.id} className="flex flex-col items-center">
              <button
                onClick={() => setOpenId(open ? null : s.id)}
                className={`w-full text-left bg-gray-900 border rounded-xl px-3 py-2.5 transition-colors ${COLOR[s.color]} ${open ? 'bg-gray-800/80' : ''}`}
              >
                <div className="flex items-center gap-2.5">
                  <span className="text-xl">{s.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="font-bold text-white text-sm">{s.title}</div>
                    <div className="text-gray-400 text-xs">{s.subtitle}</div>
                  </div>
                  <span className={`text-gray-500 transition-transform ${open ? 'rotate-180' : ''}`}>▾</span>
                </div>

                {s.branch && !open && (
                  <div className="mt-1.5 text-[10px] text-red-300 bg-red-500/10 border border-red-500/30 rounded px-1.5 py-0.5 inline-block">
                    {s.branch}
                  </div>
                )}

                {open && (
                  <div className="mt-3 pt-3 border-t border-gray-700/60 space-y-2">
                    <DetailRow label="Ne demek">{s.what}</DetailRow>
                    <DetailRow label="Neye bak">{s.look}</DetailRow>

                    {s.terms && (
                      <div className="bg-gray-800/60 rounded-lg p-2.5 space-y-2">
                        <div className="text-xs text-gray-500 font-bold">📐 Terimler ve sayılar</div>
                        {s.terms.map((tm) => (
                          <div key={tm.t} className="text-sm">
                            <span className="text-white font-semibold">{tm.t}:</span>{' '}
                            <span className="text-gray-300">{tm.d}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    <DetailRow label="Nerede">{s.where}</DetailRow>
                    <DetailRow label="💡 İpucu">{s.tip}</DetailRow>
                    {s.branch && (
                      <DetailRow label="⛔ Dal">{s.branchNote || cfg.branchDefault}</DetailRow>
                    )}
                  </div>
                )}
              </button>

              {i < steps.length - 1 && <span className="text-gray-600 text-lg leading-none my-1">↓</span>}
            </div>
          );
        })}
      </div>

      <p className="text-[11px] text-gray-600 text-center mt-4">
        Buradaki sayılar kabaca yol gösterici sınırlardır, sektöre göre değişir. Yatırım tavsiyesi değildir.
      </p>
    </div>
  );
}
