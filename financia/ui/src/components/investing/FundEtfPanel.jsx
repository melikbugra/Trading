import { useEffect, useMemo, useState } from 'react';
import { useToast } from '../../contexts/ToastContext';

const API_BASE = import.meta.env.VITE_API_BASE || '';
const fmt = (v, d = 2) => v == null ? '—' : Number(v).toLocaleString('tr-TR', { maximumFractionDigits: d });
const scoreCls = (v) => v == null ? 'text-gray-500' : v >= 70 ? 'text-green-400' : v >= 55 ? 'text-blue-400' : v >= 40 ? 'text-yellow-400' : 'text-red-400';
const flag = (market) => market === 'us' ? '🇺🇸' : '🇹🇷';

export default function FundEtfPanel() {
  const { addToast } = useToast();
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ ticker: '', market: 'us', asset_type: 'etf' });
  const [query, setQuery] = useState('');
  const [marketFilter, setMarketFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [selected, setSelected] = useState(null);
  const [buy, setBuy] = useState({ units: '', cost_basis: '' });

  const load = async () => {
    try {
      const res = await fetch(`${API_BASE}/investing/funds/screener`);
      const data = await res.json();
      setResults(data.results || []);
    } catch { addToast('Fon/ETF sonuçları yüklenemedi', 'error'); }
  };

  useEffect(() => { load(); }, []);

  const scan = async (body, label) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/investing/funds/scan`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Tarama başarısız');
      addToast(`${label}: ${data.valid}/${data.scanned} fon analiz edildi`, data.valid ? 'success' : 'error');
      await load();
    } catch (error) { addToast(error.message || 'Tarama başarısız', 'error'); }
    finally { setLoading(false); }
  };

  const analyzeOne = (e) => {
    e.preventDefault();
    if (!form.ticker.trim()) return;
    scan({ tickers: [form.ticker], market: form.market, asset_type: form.asset_type }, form.ticker.toUpperCase());
  };

  const categories = useMemo(() => [...new Set(results.map((r) => r.category).filter(Boolean))].sort(), [results]);
  const q = query.trim().toLowerCase();
  const filtered = results.filter((row) =>
    (marketFilter === 'all' || row.market === marketFilter) &&
    (typeFilter === 'all' || row.asset_type === typeFilter) &&
    (categoryFilter === 'all' || row.category === categoryFilter) &&
    (!q || `${row.ticker} ${row.name || ''} ${row.category || ''}`.toLowerCase().includes(q))
  );

  const addWatchlist = async (row) => {
    const res = await fetch(`${API_BASE}/investing/funds/watchlist`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker: row.ticker, market: row.market, asset_type: row.asset_type }),
    });
    const data = await res.json().catch(() => ({}));
    addToast(res.ok ? 'Fon/ETF izleme listesine eklendi' : (data.detail || 'Eklenemedi'), res.ok ? 'success' : 'error');
  };

  const addPortfolio = async (e) => {
    e.preventDefault();
    if (!selected || !buy.units || !buy.cost_basis) return;
    const res = await fetch(`${API_BASE}/investing/funds/holdings`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ticker: selected.ticker, market: selected.market, asset_type: selected.asset_type,
        units: parseFloat(buy.units), cost_basis: parseFloat(buy.cost_basis),
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok) {
      addToast(data.merged ? 'Fon/ETF adedi ve ortalama maliyeti güncellendi' : 'Fon/ETF portföye eklendi', 'success');
      setBuy({ units: '', cost_basis: '' });
    } else addToast(data.detail || 'Portföye eklenemedi', 'error');
  };

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-4">
        <button disabled={loading} onClick={() => scan({ universe: 'us_etf' }, 'ABD ETF')} className="px-3 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 rounded text-sm font-bold text-white">🇺🇸 Temel ETF’leri Tara</button>
        <button disabled={loading} onClick={() => scan({ universe: 'us_fund', asset_type: 'fund' }, 'Endeks fonları')} className="px-3 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-700 rounded text-sm font-bold text-white">📚 Endeks Fonlarını Tara</button>
        <button disabled={loading} onClick={() => scan({ universe: 'bist_etf', market: 'bist', asset_type: 'etf' }, 'BIST ETF')} className="px-3 py-2 bg-red-600 hover:bg-red-500 disabled:bg-gray-700 rounded text-sm font-bold text-white">🇹🇷 BIST ETF’lerini Tara</button>
        {loading && <span className="text-xs text-gray-400 self-center animate-pulse">Analiz ediliyor…</span>}
      </div>

      <form onSubmit={analyzeOne} className="bg-gray-900 border border-gray-800 rounded-lg p-3 mb-4 flex flex-wrap gap-2 items-end">
        <div><label className="block text-xs text-gray-500 mb-1">Pazar</label><select value={form.market} onChange={(e) => setForm({ ...form, market: e.target.value })} className="bg-gray-800 border border-gray-700 text-white rounded px-2 py-2 text-sm"><option value="us">🇺🇸 ABD</option><option value="bist">🇹🇷 BIST</option></select></div>
        <div><label className="block text-xs text-gray-500 mb-1">Tür</label><select value={form.asset_type} onChange={(e) => setForm({ ...form, asset_type: e.target.value })} className="bg-gray-800 border border-gray-700 text-white rounded px-2 py-2 text-sm"><option value="etf">ETF</option><option value="fund">Fon</option></select></div>
        <div><label className="block text-xs text-gray-500 mb-1">Kod</label><input value={form.ticker} onChange={(e) => setForm({ ...form, ticker: e.target.value.toUpperCase() })} placeholder={form.market === 'us' ? 'VOO / VFIAX' : 'GLDTR'} className="bg-gray-800 border border-gray-700 text-white rounded px-3 py-2 text-sm font-mono w-44" /></div>
        <button disabled={loading} className="px-3 py-2 bg-green-600 hover:bg-green-500 disabled:bg-gray-700 rounded text-sm font-bold text-white">Analiz Et</button>
        <span className="text-[11px] text-gray-500 self-center">Türkiye yatırım fonlarında Yahoo verisi olmayan kodlar analiz edilemeyebilir; ETF kodları desteklenir.</span>
      </form>

      <div className="flex flex-wrap gap-2 mb-2">
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="🔎 Kod / ad / kategori" className="bg-gray-800 border border-gray-700 text-white rounded px-2 py-1 text-xs w-48" />
        <select value={marketFilter} onChange={(e) => setMarketFilter(e.target.value)} className="bg-gray-800 border border-gray-700 text-gray-300 rounded px-2 py-1 text-xs"><option value="all">Tüm pazarlar</option><option value="us">ABD</option><option value="bist">BIST</option></select>
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="bg-gray-800 border border-gray-700 text-gray-300 rounded px-2 py-1 text-xs"><option value="all">Fon + ETF</option><option value="etf">ETF</option><option value="fund">Fon</option></select>
        <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} className="bg-gray-800 border border-gray-700 text-gray-300 rounded px-2 py-1 text-xs"><option value="all">Tüm kategoriler</option>{categories.map((c) => <option key={c}>{c}</option>)}</select>
        <span className="text-xs text-gray-500 self-center">{filtered.length} sonuç</span>
      </div>

      <div className="overflow-x-auto border border-gray-800 rounded-lg">
        <table className="w-full text-sm">
          <thead className="bg-gray-900 text-gray-500"><tr><th className="text-left px-3 py-2">Fon / ETF</th><th className="text-left px-3 py-2">Kategori</th><th className="text-right px-3 py-2">1Y</th><th className="text-right px-3 py-2">3Y yıllık</th><th className="text-right px-3 py-2">Oynaklık</th><th className="text-right px-3 py-2">Maks. düşüş</th><th className="text-right px-3 py-2">Gider</th><th className="text-right px-3 py-2">Puan</th><th className="px-3 py-2"></th></tr></thead>
          <tbody>{filtered.map((row) => { const m = row.metrics || {}; return (
            <tr key={row.ticker} onClick={() => { setSelected(row); setBuy({ units: '', cost_basis: row.price == null ? '' : String(row.price) }); }} className="border-t border-gray-800 hover:bg-gray-800/40 cursor-pointer">
              <td className="px-3 py-2"><div className="font-mono font-bold text-white">{flag(row.market)} {row.symbol || row.ticker.replace('.IS', '')} <span className="text-[10px] text-gray-500 uppercase">{row.asset_type}</span></div><div className="text-[11px] text-gray-500 max-w-[220px] truncate">{row.name}</div></td>
              <td className="px-3 py-2 text-xs text-gray-400 max-w-[160px] truncate">{row.category || '—'}</td>
              <td className={`px-3 py-2 text-right font-mono ${(m.return_1y ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>{m.return_1y == null ? '—' : `%${fmt(m.return_1y)}`}</td>
              <td className={`px-3 py-2 text-right font-mono ${(m.return_3y ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>{m.return_3y == null ? '—' : `%${fmt(m.return_3y)}`}</td>
              <td className="px-3 py-2 text-right font-mono text-gray-300">{m.volatility_1y == null ? '—' : `%${fmt(m.volatility_1y)}`}</td>
              <td className="px-3 py-2 text-right font-mono text-red-300">{m.max_drawdown_3y == null ? '—' : `%${fmt(m.max_drawdown_3y)}`}</td>
              <td className="px-3 py-2 text-right font-mono text-gray-300">{m.expense_ratio == null ? '—' : `%${fmt(m.expense_ratio, 3)}`}</td>
              <td className={`px-3 py-2 text-right font-mono font-bold ${scoreCls(row.score)}`}>{row.score == null ? '—' : row.score}</td>
              <td className="px-3 py-2 text-right"><button onClick={(e) => { e.stopPropagation(); addWatchlist(row); }} className="text-purple-400 hover:text-purple-300 text-xs">⭐ İzle</button></td>
            </tr>
          ); })}</tbody>
        </table>
        {!filtered.length && <div className="text-center text-gray-500 py-14">Henüz sonuç yok. Bir evren tara veya fon kodu analiz et.</div>}
      </div>

      {selected && <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={() => setSelected(null)}><div onClick={(e) => e.stopPropagation()} className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-2xl p-5 space-y-4">
        <div className="flex justify-between"><div><h3 className="text-lg font-bold text-white">{flag(selected.market)} {selected.symbol || selected.ticker} — {selected.name}</h3><p className="text-xs text-gray-500">{selected.category || 'Kategori yok'} · {selected.label}</p></div><button onClick={() => setSelected(null)} className="text-gray-400 hover:text-white text-xl">✕</button></div>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">{Object.entries(selected.components || {}).map(([key, value]) => <div key={key} className="bg-gray-800/60 rounded p-2 text-center"><div className="text-[10px] text-gray-500">{{ performance: 'Getiri', risk: 'Risk', cost: 'Maliyet', trend: 'Trend', income: 'Gelir' }[key] || key}</div><div className={`font-bold ${scoreCls(value)}`}>{value == null ? '—' : Math.round(value)}</div></div>)}</div>
        <div className="text-sm text-gray-300 space-y-1">{(selected.reasons || []).map((r, i) => <div key={i}>• {r}</div>)}</div>
        <div className={`text-sm font-bold ${scoreCls(selected.score)}`}>Uzun vade kararı: {selected.portfolio_action} · {selected.score ?? '—'}/100</div>
        <form onSubmit={addPortfolio} className="flex flex-wrap items-end gap-2 border-t border-gray-800 pt-3"><div><label className="block text-xs text-gray-500 mb-1">Adet</label><input type="number" step="any" value={buy.units} onChange={(e) => setBuy({ ...buy, units: e.target.value })} className="w-28 bg-gray-800 border border-gray-700 rounded px-2 py-2 text-white font-mono" /></div><div><label className="block text-xs text-gray-500 mb-1">Maliyet ({selected.currency})</label><input type="number" step="any" value={buy.cost_basis} onChange={(e) => setBuy({ ...buy, cost_basis: e.target.value })} className="w-32 bg-gray-800 border border-gray-700 rounded px-2 py-2 text-white font-mono" /></div><button className="px-3 py-2 bg-blue-600 hover:bg-blue-500 rounded text-white text-sm font-bold">Portföye Ekle</button><button type="button" onClick={() => addWatchlist(selected)} className="px-3 py-2 bg-purple-600 hover:bg-purple-500 rounded text-white text-sm font-bold">İzlemeye Ekle</button></form>
      </div></div>}
    </div>
  );
}
