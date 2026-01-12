import { X, TrendingUp, TrendingDown, Minus } from 'lucide-react';

export default function DetailsModal({ item, onClose }) {
    if (!item) return null;

    const { final_score, category_scores, indicator_details } = item;

    const getBadgeColor = (decision) => {
        switch (decision) {
            case 'STRONG BUY': return 'bg-green-500 text-black font-bold';
            case 'BUY': return 'bg-green-600/50 text-green-200';
            case 'STRONG SELL': return 'bg-red-500 text-black font-bold';
            case 'SELL': return 'bg-red-600/50 text-red-200';
            default: return 'bg-gray-600/50 text-gray-300';
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div className="bg-gray-900 border border-gray-700 w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-2xl shadow-2xl relative">

                {/* Header */}
                <div className="sticky top-0 bg-gray-900/95 backdrop-blur border-b border-gray-800 p-6 flex justify-between items-center z-10">
                    <div>
                        <h2 className="text-3xl font-black">{item.ticker.replace('.IS', '')}</h2>
                        <div className="flex items-center gap-4 mt-2">
                            <div className="text-sm opacity-60">SKOR (PUAN)</div>
                            <div className={`px-3 py-1 rounded text-lg font-bold ${final_score >= 60 ? 'bg-green-500 text-black' : final_score <= 40 ? 'bg-red-500 text-black' : 'bg-yellow-500 text-black'}`}>
                                {final_score ? final_score.toFixed(2) : '0.00'} / 100
                            </div>
                        </div>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-gray-800 rounded-full transition">
                        <X size={32} />
                    </button>
                </div>

                <div className="p-6 space-y-8">
                    {/* Categories */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        {category_scores && Object.entries(category_scores).map(([cat, score]) => (
                            <div key={cat} className="bg-gray-800/50 p-4 rounded-xl border border-gray-700">
                                <div className="text-xs uppercase tracking-wider opacity-60 mb-2">
                                    {cat === 'Volume' ? 'HACİM' : cat === 'Other' ? 'DİĞER' : cat}
                                </div>
                                <div className="text-2xl font-mono">{score.toFixed(1)}</div>
                                <div className="w-full h-1 bg-gray-700 mt-2 rounded">
                                    <div className={`h-full rounded ${score > 50 ? 'bg-green-500' : 'bg-red-500'}`} style={{ width: `${score}%` }}></div>
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Indicators Table */}
                    <div>
                        <h3 className="text-xl font-bold mb-4">Teknik İndikatör Detayları</h3>
                        <div className="overflow-x-auto rounded-lg border border-gray-800">
                            <table className="w-full text-left bg-gray-900">
                                <thead className="bg-gray-800 text-gray-400 text-xs uppercase">
                                    <tr>
                                        <th className="p-4">İndikatör</th>
                                        <th className="p-4">Değer</th>
                                        <th className="p-4">Sinyal</th>
                                        <th className="p-4">Uyumsuzluk</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-800">
                                    {indicator_details && indicator_details.map((row, idx) => (
                                        <tr key={idx} className="hover:bg-gray-800/50 transition">
                                            <td className="p-4 font-mono text-blue-300">{row.Indicator}</td>
                                            <td className="p-4 font-mono opacity-80">
                                                {row.Value || '-'}
                                            </td>
                                            <td className="p-4">
                                                <span className={`px-2 py-1 rounded text-xs ${getBadgeColor(row.Decision)}`}>
                                                    {row.Decision}
                                                </span>
                                            </td>
                                            <td className="p-4">
                                                {row.Divergence === 1 && <span className="text-green-400 text-xs px-2 py-1 bg-green-900/30 rounded border border-green-500/30">Pozitif Uyum (Dip)</span>}
                                                {row.Divergence === -1 && <span className="text-red-400 text-xs px-2 py-1 bg-red-900/30 rounded border border-red-500/30">Negatif Uyum (Tepe)</span>}
                                                {row.Divergence === 0 && <span className="text-gray-500 text-xs text-opacity-30">Yok</span>}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
