import { useState } from 'react';
import { useToast } from '../../contexts/ToastContext';

const API_BASE = import.meta.env.VITE_API_BASE || '';
const fmt = (v, d = 2) => v == null ? '—' : Number(v).toLocaleString('tr-TR', { maximumFractionDigits: d });
const actionCls = (action) => action === 'TUT' ? 'text-green-400' : action === 'DÜŞÜŞTE KADEMELİ AL' ? 'text-blue-400' : action === 'KADEMELİ AZALT' ? 'text-red-400' : 'text-yellow-400';

export default function FundHoldingsTable({ holdings = [], onChanged }) {
  const { addToast } = useToast();
  const [loading, setLoading] = useState(false);
  const [selling, setSelling] = useState(null);
  const [units, setUnits] = useState('');

  const analyze = async () => {
    if (!holdings.length) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/investing/funds/scan`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tickers: holdings.map((h) => h.ticker) }),
      });
      const data = await res.json().catch(() => ({}));
      addToast(res.ok ? `${data.valid} fon/ETF analiz edildi` : (data.detail || 'Analiz başarısız'), res.ok ? 'success' : 'error');
      if (res.ok) onChanged?.();
    } catch { addToast('Fon/ETF analizi başarısız', 'error'); }
    finally { setLoading(false); }
  };

  const sell = async (e) => {
    e.preventDefault();
    const amount = parseFloat(units);
    if (!selling || !Number.isFinite(amount) || amount <= 0 || amount > selling.units) return;
    const res = await fetch(`${API_BASE}/investing/funds/holdings/${selling.id}/sell`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ units: amount }),
    });
    if (res.ok) { addToast('Fon/ETF satışı portföye işlendi', 'success'); setSelling(null); onChanged?.(); }
    else addToast('Satış kaydedilemedi', 'error');
  };

  const remove = async (id) => {
    const res = await fetch(`${API_BASE}/investing/funds/holdings/${id}`, { method: 'DELETE' });
    if (res.ok) onChanged?.(); else addToast('Silinemedi', 'error');
  };

  return <div className="mt-6">
    <div className="flex items-center gap-2 mb-2"><h3 className="text-sm font-bold text-pink-300">🧺 Fon & ETF Portföyü</h3><span className="text-xs text-gray-500">{holdings.length} pozisyon</span><button onClick={analyze} disabled={loading || !holdings.length} className="ml-auto px-3 py-1.5 bg-pink-700 hover:bg-pink-600 disabled:bg-gray-800 text-white rounded text-xs font-bold">{loading ? 'Analiz ediliyor…' : '🔄 Fonları Analiz Et'}</button></div>
    {!holdings.length ? <div className="text-gray-500 text-center py-8 border border-dashed border-gray-800 rounded-lg">Fon & ETF sekmesinden portföye fon ekleyebilirsin.</div> :
      <div className="overflow-x-auto border border-gray-800 rounded-lg"><table className="w-full text-sm"><thead className="bg-gray-900 text-gray-500"><tr><th className="text-left px-3 py-2">Fon / ETF</th><th className="text-left px-3 py-2">Kategori</th><th className="text-left px-3 py-2">Nakit dağıtım</th><th className="text-right px-3 py-2">Adet</th><th className="text-right px-3 py-2">Maliyet</th><th className="text-right px-3 py-2">Fiyat</th><th className="text-right px-3 py-2">Değer</th><th className="text-right px-3 py-2">K/Z</th><th className="text-right px-3 py-2">Ağırlık</th><th className="text-right px-3 py-2">Uzun Vade</th><th className="px-3 py-2"></th></tr></thead>
        <tbody>{holdings.map((h) => <tr key={h.id} className="border-t border-gray-800 hover:bg-gray-800/30"><td className="px-3 py-2"><div className="text-white font-mono font-bold">{h.market === 'us' ? '🇺🇸' : '🇹🇷'} {h.symbol} <span className="text-[10px] text-gray-500 uppercase">{h.asset_type}</span></div><div className="text-[10px] text-gray-500 max-w-[180px] truncate">{h.analysis?.name}</div></td><td className="px-3 py-2 text-xs text-gray-400 max-w-[150px] truncate">{h.analysis?.category || '—'}</td><td className={`px-3 py-2 text-xs ${h.analysis?.distributes_cash ? 'text-green-400' : 'text-gray-500'}`} title={h.analysis?.distribution_status}>{h.analysis?.distribution_status || 'Bilinmiyor'}</td><td className="px-3 py-2 text-right font-mono">{fmt(h.units, 4)}</td><td className="px-3 py-2 text-right font-mono text-gray-400">{h.currency}{fmt(h.cost_basis, 4)}</td><td className="px-3 py-2 text-right font-mono">{h.price == null ? '—' : `${h.currency}${fmt(h.price, 4)}`}</td><td className="px-3 py-2 text-right font-mono text-white">{h.market_value == null ? '—' : `${h.currency}${fmt(h.market_value)}`}</td><td className={`px-3 py-2 text-right font-mono font-bold ${(h.pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>{h.pnl == null ? '—' : `${h.pnl >= 0 ? '+' : ''}${fmt(h.pnl)} (%${fmt(h.pnl_pct)})`}</td><td className="px-3 py-2 text-right font-mono text-gray-400">{h.weight == null ? '—' : `%${fmt(h.weight, 1)}`}</td><td className={`px-3 py-2 text-right text-xs font-bold ${actionCls(h.analysis?.portfolio_action)}`} title={h.analysis?.reasons?.join(' · ')}>{h.analysis?.portfolio_action || 'Analiz bekliyor'}<div className="text-[10px] text-gray-500 font-mono">{h.analysis?.score == null ? '' : `${h.analysis.score}/100`}</div></td><td className="px-3 py-2 text-right whitespace-nowrap"><button onClick={() => { setSelling(h); setUnits(''); }} className="text-orange-400 hover:text-orange-300 text-xs mr-2">Sat</button><button onClick={() => remove(h.id)} className="text-red-400 hover:text-red-300 text-xs">Sil</button></td></tr>)}</tbody>
      </table></div>}
    {selling && <div className="fixed inset-0 z-[60] bg-black/70 flex items-center justify-center p-4" onClick={() => setSelling(null)}><form onSubmit={sell} onClick={(e) => e.stopPropagation()} className="bg-gray-900 border border-gray-700 rounded-xl p-5 w-full max-w-sm space-y-3"><div className="flex justify-between"><h3 className="font-bold text-white">{selling.symbol} — Kademeli Satış</h3><button type="button" onClick={() => setSelling(null)} className="text-gray-400">✕</button></div><p className="text-xs text-gray-500">Mevcut adet: {fmt(selling.units, 4)}</p><input type="number" min="0" max={selling.units} step="any" autoFocus value={units} onChange={(e) => setUnits(e.target.value)} className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-2 text-white font-mono" placeholder="Satılacak adet" /><div className="flex justify-end gap-2"><button type="button" onClick={() => setSelling(null)} className="px-3 py-2 bg-gray-700 rounded text-white text-sm">İptal</button><button className="px-3 py-2 bg-orange-600 rounded text-white text-sm font-bold">Satışı Kaydet</button></div></form></div>}
  </div>;
}
