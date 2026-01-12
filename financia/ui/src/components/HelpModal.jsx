import { useState } from 'react';
import { X, BookOpen, Activity, BarChart2, AlertTriangle, Layers } from 'lucide-react';

export default function HelpModal({ onClose }) {
    const [activeTab, setActiveTab] = useState('strategy');

    const MENU_ITEMS = [
        { id: 'strategy', label: 'İşlem Stratejisi', icon: <BookOpen size={18} /> },
        { id: 'indicators', label: 'İndikatör Rehberi', icon: <Activity size={18} /> },
        { id: 'classification', label: 'Zaman Dilimleri', icon: <Layers size={18} /> },
        { id: 'scoring', label: 'Puanlama Sistemi', icon: <BarChart2 size={18} /> },
        { id: 'divergence', label: 'Uyumsuzluk (Divergence)', icon: <AlertTriangle size={18} /> },
    ];

    const renderContent = () => {
        switch (activeTab) {
            case 'strategy':
                return (
                    <div className="space-y-6">
                        <h2 className="text-2xl font-bold text-green-400">RL Trading Bot Strateji Rehberi</h2>

                        <div className="bg-gray-800/50 p-4 rounded-lg border border-gray-700">
                            <h3 className="font-bold text-lg mb-2 text-yellow-500">Temel Felsefe: "Bot Önerir, İnsan Onaylar"</h3>
                            <p className="text-gray-300">
                                Bu bot bir <strong>"Otomatik Pilot"</strong> değil, 7/24 piyasayı tarayan bir <strong>"Radar"</strong> sistemidir.
                                Botun görevi fırsatları bulmak, sizin göreviniz ise <strong>CANLI FİYATI</strong> kontrol edip tetiği çekmektir.
                            </p>
                        </div>

                        <div>
                            <h3 className="text-xl font-bold mb-3">15 Dakika Gecikme Yönetimi</h3>
                            <ul className="list-disc pl-5 space-y-2 text-gray-300">
                                <li>Bot ücretsiz veri kullandığı için sinyaller 15 dakika gecikmelidir.</li>
                                <li><strong>Örnek:</strong> 14:15'te gelen "THYAO AL (100.00)" sinyali, aslında 14:00 verisine dayanır.</li>
                                <li><strong>Aksiyon:</strong> Aracı kurum uygulamanızdan CANLI fiyata bakın.</li>
                                <li>Fiyat ~100.10 ise: <strong>GİR</strong> (Trend devam ediyor).</li>
                                <li>Fiyat &gt; 103.00 ise: <strong>BEKLE</strong> (Fiyat uçmuş, geç kaldın).</li>
                                <li>Fiyat &lt; 98.00 ise: <strong>İPTAL</strong> (Sinyal bozulmuş).</li>
                            </ul>
                        </div>

                        <div>
                            <h3 className="text-xl font-bold mb-3">Altın Kural: Limit Emir</h3>
                            <p className="mb-2 text-gray-300">Asla Piyasa Emri (Market Order) kullanmayın. Her zaman <strong>Limit Emir</strong> kullanın.</p>
                            <table className="w-full text-left text-sm text-gray-300 border border-gray-700">
                                <thead className="bg-gray-800 text-gray-400">
                                    <tr>
                                        <th className="p-2">Durum</th>
                                        <th className="p-2">Strateji</th>
                                        <th className="p-2">Limit Emir Fiyatı</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-700">
                                    <tr>
                                        <td className="p-2">Normal Alım</td>
                                        <td className="p-2 text-green-400 font-bold">AL</td>
                                        <td className="p-2">Canlı Fiyat + 2 kademe (Hemen almak için)</td>
                                    </tr>
                                    <tr>
                                        <td className="p-2">Fiyat Uçmuş</td>
                                        <td className="p-2 text-yellow-400 font-bold">BEKLE</td>
                                        <td className="p-2">Botun Fiyatı (Geri çekilme bekle)</td>
                                    </tr>
                                    <tr>
                                        <td className="p-2">Normal Satım</td>
                                        <td className="p-2 text-red-400 font-bold">SAT</td>
                                        <td className="p-2">Canlı Fiyat - 2 kademe (Hemen çıkmak için)</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                );

            case 'indicators':
                return (
                    <div className="space-y-6">
                        <h2 className="text-2xl font-bold text-blue-400">Teknik İndikatörler Sözlüğü</h2>
                        <p className="text-gray-400 mb-4">Bu sistem piyasayı analiz etmek için 20'den fazla indikatörü aynı anda kullanır.</p>

                        <div className="grid gap-4 bg-gray-900/50 p-2 rounded max-h-[60vh] overflow-y-auto">
                            <IndicatorGroup title="Trend Takipçileri (Yön Belirleyiciler)">
                                <IndicatorCard name="SuperTrend" desc="En popüler trend takipçisi. Fiyat bu çizginin üzerindeyse yön YUKARI, altındaysa AŞAĞI kabul edilir." logic="Fiyat üstüne çıkarsa AL." />
                                <IndicatorCard name="Ichimoku Cloud" desc="Japon teknik analiz sanatı. Bulutun üzerinde olmak güvenli yükseliş, altında olmak düşüş bölgesidir." logic="Fiyat > Bulut ve Tenkan > Kijun ise AL." />
                                <IndicatorCard name="Parabolic SAR" desc="Zaman/Fiyat dönüş noktalarını gösteren noktalar. Trend değişimlerini erken yakalar." logic="Noktalar fiyatın altına geçerse AL." />
                                <IndicatorCard name="Alligator" desc="Bill Williams'ın Timsahı. Çenesi, Dişleri ve Dudakları (MA'lar) açıldığında trend başlar (Timsah Besleniyor)." logic="Yeşil > Kırmızı > Mavi ise AL (Açlık)." />
                                <IndicatorCard name="KAMA" desc="Kaufman Adaptive MA. Piyasa gürültüsünü filtreleyen, oynaklığa göre hızlanan akıllı ortalama." logic="Fiyat KAMA'yı yukarı keserse AL." />
                                <IndicatorCard name="DEMA" desc="Double EMA. Gecikmesi azaltılmış hızlı hareketli ortalama." logic="Kısa vade (Hızlı) Uzun vadeyi (Yavaş) keserse AL." />
                                <IndicatorCard name="MA (SMA)" desc="Basit Hareketli Ortalama. Genel yönü gösterir." logic="Fiyat ortalamanın üstüneyse AL." />
                            </IndicatorGroup>

                            <IndicatorGroup title="Momentum (Güç Göstergeleri)">
                                <IndicatorCard name="RSI" desc="Göreceli Güç Endeksi. Fiyatın aşırı şişip şişmediğini gösterir." logic="<30 Ucuz (AL), >70 Pahalı (SAT)." />
                                <IndicatorCard name="MACD" desc="Trendin gücünü ve yönünü ölçer. Sıfırın üzerinde olması boğa piyasasını teyit eder." logic="MACD çizgisi Sinyal çizgisini yukarı keserse AL." />
                                <IndicatorCard name="Stochastic" desc="Fiyatın kapanışının son aralığa göre nerede olduğunu ölçer. Dönüşleri RSI'dan hızlı yakalar." logic="RSI gibi, 20 altından dönüş AL." />
                                <IndicatorCard name="StochRSI" desc="RSI'ın Stochastiği. Çok hassastır, ani tepkiler verir." logic="Çok hızlı AL/SAT sinyali üretir." />
                                <IndicatorCard name="Williams %R" desc="Aşırı alım/satım bölgelerini gösterir. Negatif değerlerle çalışır." logic="-80 altı ucuz (AL), -20 üstü pahalı (SAT)." />
                                <IndicatorCard name="Fisher Transform" desc="Fiyatı normal dağılıma dönüştürerek dönüşleri keskinleştirir." logic="Sinyal çizgisini yukarı keserse AL." />
                                <IndicatorCard name="WaveTrend" desc="Dalga hareketlerini takip eden modern osilatör." logic="Diplerde yeşil nokta (kesişim) AL sinyalidir." />
                                <IndicatorCard name="Awesome Oscillator" desc="Piyasa ivmesini ölçer. Sıfır çizgisinin üstüne çıkış alım gücünü gösterir." logic="Kırmızıdan Yeşile dönüş veya Sıfır geçişi AL." />
                                <IndicatorCard name="Aroon" desc="Yeni trendin gücünü ölçer. 'Up' çizgisi 100'e yakınsa trend çok güçlüdür." logic="Aroon Up, Aroon Down'ı yukarı keserse AL." />
                                <IndicatorCard name="Median" desc="Fiyatın medyan (orta) değerden sapmasını gösterir." logic="Mor bant içine dönüş AL sinyali olabilir." />
                            </IndicatorGroup>

                            <IndicatorGroup title="Hacim ve Para Akışı">
                                <IndicatorCard name="MFI (Money Flow Index)" desc="Hacim ağırlıklı RSI. Paranın hisseye girip girmediğini gösterir." logic="RSI gibi, ama hacim destekli. <20 AL." />
                                <IndicatorCard name="CMF (Chaikin MF)" desc="Kurumsal para girişini (akümülasyon) tespit etmeye çalışır." logic="Sıfırın üstü Pozitif Para Girişi (AL)." />
                                <IndicatorCard name="Demand Index" desc="Alım ve Satım baskısını karşılaştırır." logic="Sıfırın üstüne çıkış Alım Baskısı (Demand) artıyor demektir." />
                            </IndicatorGroup>

                            <IndicatorGroup title="Volatilite ve Diğerleri">
                                <IndicatorCard name="Bollinger Bands" desc="Fiyatın standart sapma bantları. Bantlar daraldığında patlama yakın demektir." logic="Alt banda çarpıp dönmesi AL fırsatıdır." />
                                <IndicatorCard name="Gator" desc="Alligator'un histogram hali. Trendin gücünü renklerle gösterir." logic="Yeşil barlar trendin güçlendiğini (Timsah yiyor) gösterir." />
                            </IndicatorGroup>
                        </div>
                    </div>
                );

            case 'classification':
                return (
                    <div className="space-y-6">
                        <h2 className="text-2xl font-bold text-purple-400">Vade & İndikatör Uyumu</h2>
                        <p className="text-gray-400">Hangi indikatör hangi zaman diliminde daha etkilidir?</p>

                        <div className="space-y-4">
                            <div className="bg-gray-800 p-4 rounded-lg">
                                <h3 className="font-bold text-green-400 mb-2">Kısa Vade (Scalping / 4 Saatlik)</h3>
                                <p className="text-sm text-gray-300 mb-2">Hızlı tepki veren, dönüşleri hemen yakalayan indikatörler.</p>
                                <div className="flex flex-wrap gap-2">
                                    <Badge>RSI</Badge> <Badge>Stochastic</Badge> <Badge>Williams %R</Badge>
                                    <Badge>WaveTrend</Badge> <Badge>Fisher</Badge> <Badge>StochRSI</Badge>
                                </div>
                            </div>

                            <div className="bg-gray-800 p-4 rounded-lg">
                                <h3 className="font-bold text-blue-400 mb-2">Orta Vade (Swing / Günlük)</h3>
                                <p className="text-sm text-gray-300 mb-2">Ana trendi takip eden, gürültüden daha az etkilenenler.</p>
                                <div className="flex flex-wrap gap-2">
                                    <Badge>MACD</Badge> <Badge>SuperTrend</Badge> <Badge>Awesome Osc</Badge>
                                    <Badge>Aroon</Badge> <Badge>Demand Index</Badge> <Badge>MFI</Badge>
                                </div>
                            </div>

                            <div className="bg-gray-800 p-4 rounded-lg">
                                <h3 className="font-bold text-yellow-400 mb-2">Uzun Vade (Yatırım / Haftalık)</h3>
                                <p className="text-sm text-gray-300 mb-2">Büyük resmi gösteren, yavaş ama güvenilir indikatörler.</p>
                                <div className="flex flex-wrap gap-2">
                                    <Badge>SMA 50/200</Badge> <Badge>Ichimoku</Badge> <Badge>Parabolic SAR</Badge>
                                    <Badge>Alligator</Badge> <Badge>KAMA</Badge>
                                </div>
                            </div>
                        </div>
                    </div>
                );

            case 'scoring':
                return (
                    <div className="space-y-6">
                        <h2 className="text-2xl font-bold text-orange-400">Puanlama Algoritması</h2>
                        <p className="text-gray-300">
                            "Skor" (0-100), 23 farklı indikatörün oylarının ağırlıklı ortalaması ile hesaplanır.
                        </p>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="bg-gray-800 p-4 rounded">
                                <h4 className="font-bold text-gray-400 mb-2">Etki Ağırlıkları</h4>
                                <ul className="space-y-1 text-sm">
                                    <li><span className="text-blue-400">40%</span> Trend İndikatörleri (Yön)</li>
                                    <li><span className="text-purple-400">30%</span> Momentum (Hız/Güç)</li>
                                    <li><span className="text-yellow-400">20%</span> Hacim (Para Girişi)</li>
                                    <li><span className="text-gray-500">10%</span> Diğer (Volatilite vb.)</li>
                                </ul>
                            </div>
                            <div className="bg-gray-800 p-4 rounded">
                                <h4 className="font-bold text-gray-400 mb-2">Puan Anlamları</h4>
                                <ul className="space-y-1 text-sm">
                                    <li><span className="text-green-500 font-bold">80-100</span> GÜÇLÜ AL (Ralli)</li>
                                    <li><span className="text-green-400">60-79</span> AL (Pozitif)</li>
                                    <li><span className="text-gray-400">41-59</span> NÖTR (Kararsız)</li>
                                    <li><span className="text-red-400">21-40</span> SAT (Negatif)</li>
                                    <li><span className="text-red-500 font-bold">0-20</span> GÜÇLÜ SAT (Çöküş)</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                );

            case 'divergence':
                return (
                    <div className="space-y-6">
                        <h2 className="text-2xl font-bold text-pink-400">Uyumsuzluk (Divergence) Nedir?</h2>
                        <p className="text-gray-300">
                            Fiyat ile İndikatörün birbirine zıt hareket etmesidir. En güçlü <strong>DÖNÜŞ</strong> sinyallerinden biridir.
                        </p>

                        <div className="grid gap-6 md:grid-cols-2">
                            <div className="bg-green-900/20 border border-green-900 p-4 rounded-lg">
                                <h3 className="font-bold text-green-400 mb-2">Pozitif Uyumsuzluk (Bullish)</h3>
                                <p className="text-sm text-gray-400 mb-2">Sinyal: <strong>DİP (Yükseliş Başlangıcı)</strong></p>
                                <ul className="text-sm text-gray-300 list-disc pl-4">
                                    <li>Fiyat <strong>DAHA DÜŞÜK DİP</strong> yapar.</li>
                                    <li>İndikatör <strong>DAHA YÜKSEK DİP</strong> yapar.</li>
                                    <li>Anlamı: Satış baskısı bitiyor, alıcılar gizliden güçleniyor.</li>
                                </ul>
                            </div>

                            <div className="bg-red-900/20 border border-red-900 p-4 rounded-lg">
                                <h3 className="font-bold text-red-400 mb-2">Negatif Uyumsuzluk (Bearish)</h3>
                                <p className="text-sm text-gray-400 mb-2">Sinyal: <strong>TEPE (Düşüş Başlangıcı)</strong></p>
                                <ul className="text-sm text-gray-300 list-disc pl-4">
                                    <li>Fiyat <strong>DAHA YÜKSEK TEPE</strong> yapar.</li>
                                    <li>İndikatör <strong>DAHA DÜŞÜK TEPE</strong> yapar.</li>
                                    <li>Anlamı: Fiyat yükseliyor ama alıcı gücü tükenmiş. Düşüş yakın.</li>
                                </ul>
                            </div>
                        </div>

                        <div className="mt-8">
                            <h3 className="text-xl font-bold mb-4 text-purple-400 border-b border-gray-700 pb-2">Sinyal Kombinasyonları Rehberi</h3>
                            <div className="grid gap-6">

                                {/* BUY Signals */}
                                <div>
                                    <h4 className="font-bold text-green-400 mb-3 ml-1">A. ALIM (BUY) Sinyalleri</h4>
                                    <div className="overflow-hidden rounded-lg border border-gray-700">
                                        <table className="w-full text-left text-sm text-gray-300">
                                            <thead className="bg-gray-800 text-gray-400">
                                                <tr>
                                                    <th className="p-3">Kombinasyon</th>
                                                    <th className="p-3">Anlamı</th>
                                                    <th className="p-3">Güç</th>
                                                    <th className="p-3">Aksiyon</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-gray-700 bg-gray-800/30">
                                                <tr>
                                                    <td className="p-3 font-bold text-green-300">BUY + Pozitif Uyumsuzluk</td>
                                                    <td className="p-3">Fiyat düşüyor ama satıcı bitti. Güçlü dönüş.</td>
                                                    <td className="p-3 text-yellow-400">⭐⭐⭐⭐⭐</td>
                                                    <td className="p-3 font-bold text-green-400">KESİN AL (Cesur Ol)</td>
                                                </tr>
                                                <tr>
                                                    <td className="p-3">Sadece BUY</td>
                                                    <td className="p-3">Teknik göstergeler olumluya döndü.</td>
                                                    <td className="p-3 text-yellow-500/70">⭐⭐⭐</td>
                                                    <td className="p-3">AL (Standart)</td>
                                                </tr>
                                                <tr>
                                                    <td className="p-3 text-gray-400">BUY + Negatif Uyumsuzluk</td>
                                                    <td className="p-3">Fiyat yükselirken güç kaybediyor. Riskli.</td>
                                                    <td className="p-3 text-gray-500">⭐⭐</td>
                                                    <td className="p-3 text-orange-400">VUR-KAÇ (Tetikte Ol)</td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </div>
                                </div>

                                {/* SELL Signals */}
                                <div>
                                    <h4 className="font-bold text-red-400 mb-3 ml-1">B. SATIM (SELL) Sinyalleri</h4>
                                    <div className="overflow-hidden rounded-lg border border-gray-700">
                                        <table className="w-full text-left text-sm text-gray-300">
                                            <thead className="bg-gray-800 text-gray-400">
                                                <tr>
                                                    <th className="p-3">Kombinasyon</th>
                                                    <th className="p-3">Anlamı</th>
                                                    <th className="p-3">Güç</th>
                                                    <th className="p-3">Aksiyon</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-gray-700 bg-gray-800/30">
                                                <tr>
                                                    <td className="p-3 font-bold text-red-300">SELL + Negatif Uyumsuzluk</td>
                                                    <td className="p-3">Tepe yapıldı, alıcı bitti. Çöküş kapıda.</td>
                                                    <td className="p-3 text-red-500">💀💀💀💀💀</td>
                                                    <td className="p-3 font-bold text-red-500">HEMEN KAÇ</td>
                                                </tr>
                                                <tr>
                                                    <td className="p-3">Sadece SELL</td>
                                                    <td className="p-3">Göstergeler olumsuza döndü.</td>
                                                    <td className="p-3 text-red-400/70">💀💀💀</td>
                                                    <td className="p-3">SAT (Normal)</td>
                                                </tr>
                                                <tr>
                                                    <td className="p-3 text-gray-400">SELL + Pozitif Uyumsuzluk</td>
                                                    <td className="p-3">Düşüşte ama alıcı geliyor. Dip olabilir.</td>
                                                    <td className="p-3 text-gray-500">💀💀</td>
                                                    <td className="p-3 text-yellow-400">KADEMELİ SAT (Dikkat)</td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </div>
                                </div>

                            </div>
                        </div>
                    </div>
                );
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-md">
            {/* increased height to 90vh */}
            <div className="bg-gray-900 border border-gray-700 w-full max-w-5xl h-[90vh] rounded-2xl shadow-2xl flex overflow-hidden">

                {/* Sidebar */}
                <div className="w-64 bg-gray-900 border-r border-gray-800 p-4 flex flex-col">
                    <h2 className="text-xl font-black mb-6 px-2 text-white/50">REHBER</h2>
                    <nav className="space-y-2 flex-1">
                        {MENU_ITEMS.map((item) => (
                            <button
                                key={item.id}
                                onClick={() => setActiveTab(item.id)}
                                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition ${activeTab === item.id
                                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20'
                                    : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                                    }`}
                            >
                                {item.icon}
                                <span className="font-medium text-sm">{item.label}</span>
                            </button>
                        ))}
                    </nav>
                    <div className="text-xs text-gray-600 mt-4 px-2">
                        v1.0.3 - Gelişmiş RL Ajanı
                    </div>
                </div>

                {/* Content Area */}
                <div className="flex-1 flex flex-col min-w-0">
                    <div className="p-4 border-b border-gray-800 flex justify-end">
                        <button onClick={onClose} className="p-2 hover:bg-red-500/10 hover:text-red-400 rounded-full transition">
                            <X size={24} />
                        </button>
                    </div>
                    <div className="flex-1 overflow-y-auto p-8">
                        {renderContent()}
                    </div>
                </div>

            </div>
        </div>
    );
}

function IndicatorGroup({ title, children }) {
    return (
        <div className="mb-6">
            <h3 className="text-gray-300 font-bold mb-3 border-b border-gray-700 pb-1">{title}</h3>
            <div className="grid gap-3">
                {children}
            </div>
        </div>
    );
}

function IndicatorCard({ name, desc, logic }) {
    return (
        <div className="bg-gray-800/40 border border-gray-700 p-4 rounded-lg flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
                <h4 className="font-bold text-white text-lg">{name}</h4>
                <p className="text-sm text-gray-400">{desc}</p>
            </div>
            <div className="text-xs bg-gray-900/80 p-2 rounded text-blue-300 font-mono border border-blue-900/30 whitespace-nowrap">
                {logic}
            </div>
        </div>
    );
}

function Badge({ children }) {
    return (
        <span className="px-2 py-1 bg-gray-700 rounded text-xs text-gray-300 border border-gray-600">
            {children}
        </span>
    );
}
