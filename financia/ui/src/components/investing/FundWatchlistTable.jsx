import { useState } from 'react';
import { useToast } from '../../contexts/ToastContext';

const API_BASE = import.meta.env.VITE_API_BASE || '';
const fmt = (v, d = 2) => v == null ? '—' : Number(v).toLocaleString('tr-TR', { maximumFractionDigits: d });
const scoreCls = (v) => v == null ? 'text-gray-500' : v >= 70 ? 'text-green-400' : v >= 55 ? 'text-blue-400' : v >= 40 ? 'text-yellow-400' : 'text-red-400';

export default function FundWatchlistTable({ items = [], onChanged }) {
  const { addToast } = useToast();
  const [loading, setLoading] = useState(false);
  const analyze = async () => {
    if (!items.length) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/investing/funds/scan`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tickers: items.map((i) => i.ticker) }) });
      const data = await res.json().catch(() => ({}));
      addToast(res.ok ? `${data.valid} fon/ETF analiz edildi` : (data.detail || 'Analiz başarısız'), res.ok ? 'success' : 'error');
      if (res.ok) onChanged?.();
    } catch { addToast('Analiz başarısız', 'error'); }
    finally { setLoading(false); }
  };
  const remove = async (id) => {
    const res = await fetch(`${API_BASE}/investing/funds/watchlist/${id}`, { method: 'DELETE' });
    if (res.ok) onChanged?.(); else addToast('Silinemedi', 'error');
  };
  return <div className="mt-6"><div className="flex items-center gap-2 mb-2"><h3 className="text-sm font-bold text-pink-300">🧺 Fon & ETF İzleme Listesi</h3><span className="text-xs text-gray-500">{items.length} varlık</span><button onClick={analyze} disabled={loading || !items.length} className="ml-auto px-3 py-1.5 bg-pink-700 hover:bg-pink-600 disabled:bg-gray-800 text-white rounded text-xs font-bold">{loading ? 'Analiz ediliyor…' : '🔄 Fonları Analiz Et'}</button></div>
    {!items.length ? <div className="text-gray-500 text-center py-8 border border-dashed border-gray-800 rounded-lg">Fon & ETF sekmesinden izleme listesine fon ekleyebilirsin.</div> : <div className="overflow-x-auto border border-gray-800 rounded-lg"><table className="w-full text-sm"><thead className="bg-gray-900 text-gray-500"><tr><th className="text-left px-3 py-2">Fon / ETF</th><th className="text-left px-3 py-2">Kategori</th><th className="text-right px-3 py-2">1Y</th><th className="text-right px-3 py-2">3Y yıllık</th><th className="text-right px-3 py-2">Maks. düşüş</th><th className="text-right px-3 py-2">Gider</th><th className="text-right px-3 py-2">Puan</th><th className="px-3 py-2"></th></tr></thead><tbody>{items.map((item) => { const a = item.analysis || {}; const m = a.metrics || {}; return <tr key={item.id} className="border-t border-gray-800 hover:bg-gray-800/30"><td className="px-3 py-2"><div className="font-mono font-bold text-white">{item.market === 'us' ? '🇺🇸' : '🇹🇷'} {item.symbol} <span className="text-[10px] text-gray-500 uppercase">{item.asset_type}</span></div><div className="text-[10px] text-gray-500 max-w-[220px] truncate">{a.name}</div></td><td className="px-3 py-2 text-xs text-gray-400">{a.category || '—'}</td><td className={`px-3 py-2 text-right font-mono ${(m.return_1y ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>{m.return_1y == null ? '—' : `%${fmt(m.return_1y)}`}</td><td className={`px-3 py-2 text-right font-mono ${(m.return_3y ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>{m.return_3y == null ? '—' : `%${fmt(m.return_3y)}`}</td><td className="px-3 py-2 text-right font-mono text-red-300">{m.max_drawdown_3y == null ? '—' : `%${fmt(m.max_drawdown_3y)}`}</td><td className="px-3 py-2 text-right font-mono text-gray-300">{m.expense_ratio == null ? '—' : `%${fmt(m.expense_ratio, 3)}`}</td><td className={`px-3 py-2 text-right font-mono font-bold ${scoreCls(a.score)}`} title={a.reasons?.join(' · ')}>{a.score == null ? '—' : a.score}</td><td className="px-3 py-2 text-right"><button onClick={() => remove(item.id)} className="text-red-400 hover:text-red-300 text-xs">Sil</button></td></tr>; })}</tbody></table></div>}
  </div>;
}
