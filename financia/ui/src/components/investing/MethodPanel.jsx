import { useState } from 'react';

// Portföye hisse alma karar akışı — her kutu bir adım, tıklayınca öğretici açılır.
const STEPS = [
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
    id: 'karar',
    icon: '⚖️',
    title: '5. Karar: Al / İzle / Geç',
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
    title: '6. Pozisyon & Çeşitlendirme',
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
    title: '7. Kademeli Alım',
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
    title: '8. Takip & Gözden Geçir',
    subtitle: 'Aldıktan sonra izlemeyi sürdür',
    color: 'blue',
    what: 'Hisseyi aldıktan sonra ara sıra kontrol et. Şirketin durumu bozulduysa çıkmayı bil.',
    look: 'Yeni bilanço nasıl geldi? Temel skorlar düştü mü? Kötü haber veya temettü kesintisi var mı?',
    where: 'Portföy + Haberler + ara ara yeniden tarama.',
    tip: 'Sadece fiyat düştü diye satma. "Bu hisseyi neden almıştım?" sebebin hâlâ geçerliyse tut; sebep çürüdüyse sat.',
  },
];

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

export default function MethodPanel() {
  const [openId, setOpenId] = useState(null);

  return (
    <div className="max-w-2xl mx-auto">
      <div className="text-center mb-5">
        <h2 className="text-lg font-bold text-white">Portföye Hisse Alma Akışı</h2>
        <p className="text-gray-500 text-sm mt-1">Her adıma tıkla — ne demek olduğunu ve uygulamada nerede yapacağını sade dille anlatır.</p>
      </div>

      <div className="flex flex-col items-stretch">
        {STEPS.map((s, i) => {
          const open = openId === s.id;
          return (
            <div key={s.id} className="flex flex-col items-center">
              <button
                onClick={() => setOpenId(open ? null : s.id)}
                className={`w-full text-left bg-gray-900 border rounded-xl px-4 py-3 transition-colors ${COLOR[s.color]} ${open ? 'bg-gray-800/80' : ''}`}
              >
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{s.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="font-bold text-white text-sm">{s.title}</div>
                    <div className="text-gray-400 text-xs">{s.subtitle}</div>
                  </div>
                  {s.branch && (
                    <span className="hidden sm:inline text-[10px] text-red-300 bg-red-500/10 border border-red-500/30 rounded px-1.5 py-0.5">
                      {s.branch}
                    </span>
                  )}
                  <span className={`text-gray-500 transition-transform ${open ? 'rotate-180' : ''}`}>▾</span>
                </div>

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
                      <DetailRow label="⛔ Dal">Bu adımı geçemezse hisseyi alma listesinden çıkar.</DetailRow>
                    )}
                  </div>
                )}
              </button>

              {/* connector arrow */}
              {i < STEPS.length - 1 && <span className="text-gray-600 text-lg leading-none my-1">↓</span>}
            </div>
          );
        })}
      </div>

      <p className="text-[11px] text-gray-600 text-center mt-6">
        Buradaki sayılar kabaca yol gösterici sınırlardır, sektöre göre değişir. Bu akış genel bir rehberdir, yatırım tavsiyesi değildir.
      </p>
    </div>
  );
}
