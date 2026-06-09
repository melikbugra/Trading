import { useEffect, useState } from 'react';
import { useToast } from '../../contexts/ToastContext';
import StockReportModal from './StockReportModal';
import DiversificationCard from './DiversificationCard';
import ListFilters, { uniqueSectors } from './ListFilters';

const API_BASE = import.meta.env.VITE_API_BASE || '';

const fmt = (v, d = 2) => (v == null ? '—' : Number(v).toLocaleString('tr-TR', { minimumFractionDigits: d, maximumFractionDigits: d }));

const emptyForm = { ticker: '', market: 'bist', shares: '', cost_basis: '', purchase_date: '', notes: '' };

export default function PortfolioPanel() {
  const { addToast } = useToast();
  const [data, setData] = useState({ holdings: [], totals: [] });
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [reportTicker, setReportTicker] = useState(null);
  const [marketFilter, setMarketFilter] = useState('all');
  const [sectorFilter, setSectorFilter] = useState('all');

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/investing/holdings`);
      setData(await res.json());
    } catch {
      addToast('Portföy yüklenemedi', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const addHolding = async (e) => {
    e.preventDefault();
    if (!form.ticker || !form.shares || !form.cost_basis) {
      addToast('Hisse, adet ve maliyet zorunlu', 'error');
      return;
    }
    let ticker = form.ticker.trim().toUpperCase();
    if (form.market === 'bist' && !ticker.endsWith('.IS')) ticker += '.IS';
    try {
      const res = await fetch(`${API_BASE}/investing/holdings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker,
          market: form.market,
          shares: parseFloat(form.shares),
          cost_basis: parseFloat(form.cost_basis),
          purchase_date: form.purchase_date || null,
          notes: form.notes,
        }),
      });
      if (res.ok) {
        addToast(`${ticker} eklendi`, 'success');
        setForm(emptyForm);
        setShowForm(false);
        load();
      } else {
        addToast('Eklenemedi', 'error');
      }
    } catch {
      addToast('Eklenemedi', 'error');
    }
  };

  const removeHolding = async (id) => {
    try {
      await fetch(`${API_BASE}/investing/holdings/${id}`, { method: 'DELETE' });
      load();
    } catch { addToast('Silinemedi', 'error'); }
  };

  const sectors = uniqueSectors(data.holdings, (h) => h.sector);
  const visibleHoldings = data.holdings.filter(
    (h) => (marketFilter === 'all' || h.market === marketFilter) && (sectorFilter === 'all' || h.sector === sectorFilter)
  );

  return (
    <div>
      {/* Risk & diversification */}
      {data.holdings.length > 0 && <DiversificationCard />}

      {/* Totals */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        {data.totals?.length > 0 ? data.totals.map((t) => (
          <div key={t.currency} className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-2">
            <div className="text-xs text-gray-500">Toplam Değer ({t.currency})</div>
            <div className="text-lg font-bold text-white font-mono">{t.currency}{fmt(t.market_value)}</div>
          </div>
        )) : <div className="text-gray-500 text-sm">Henüz pozisyon yok.</div>}
        <button
          onClick={() => setShowForm((v) => !v)}
          className="ml-auto px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded text-sm font-bold"
        >
          {showForm ? '✕ Kapat' : '+ Hisse Ekle'}
        </button>
      </div>

      {/* Add form */}
      {showForm && (
        <form onSubmit={addHolding} className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-4 grid grid-cols-2 sm:grid-cols-6 gap-3 items-end">
          <div className="col-span-1">
            <label className="block text-xs text-gray-500 mb-1">Pazar</label>
            <select value={form.market} onChange={(e) => setForm({ ...form, market: e.target.value })} className="w-full bg-gray-800 border border-gray-700 text-white px-2 py-2 rounded text-sm">
              <option value="bist">🇹🇷 BIST</option>
              <option value="us">🇺🇸 ABD</option>
            </select>
          </div>
          <div className="col-span-1">
            <label className="block text-xs text-gray-500 mb-1">Hisse</label>
            <input value={form.ticker} onChange={(e) => setForm({ ...form, ticker: e.target.value })} placeholder={form.market === 'bist' ? 'THYAO' : 'AAPL'} className="w-full bg-gray-800 border border-gray-700 text-white px-2 py-2 rounded text-sm font-mono uppercase" />
          </div>
          <div className="col-span-1">
            <label className="block text-xs text-gray-500 mb-1">Adet</label>
            <input type="number" step="any" value={form.shares} onChange={(e) => setForm({ ...form, shares: e.target.value })} className="w-full bg-gray-800 border border-gray-700 text-white px-2 py-2 rounded text-sm font-mono" />
          </div>
          <div className="col-span-1">
            <label className="block text-xs text-gray-500 mb-1">Maliyet/Adet</label>
            <input type="number" step="any" value={form.cost_basis} onChange={(e) => setForm({ ...form, cost_basis: e.target.value })} className="w-full bg-gray-800 border border-gray-700 text-white px-2 py-2 rounded text-sm font-mono" />
          </div>
          <div className="col-span-1">
            <label className="block text-xs text-gray-500 mb-1">Alım Tarihi</label>
            <input type="date" value={form.purchase_date} onChange={(e) => setForm({ ...form, purchase_date: e.target.value })} className="w-full bg-gray-800 border border-gray-700 text-white px-2 py-2 rounded text-sm" />
          </div>
          <div className="col-span-1">
            <button type="submit" className="w-full px-3 py-2 bg-green-600 hover:bg-green-500 text-white rounded text-sm font-bold">Ekle</button>
          </div>
        </form>
      )}

      {/* Holdings table */}
      {loading ? (
        <div className="text-gray-400 text-center py-10">Yükleniyor…</div>
      ) : data.holdings.length === 0 ? (
        <div className="text-gray-500 text-center py-16 border border-dashed border-gray-800 rounded-lg">Portföyün boş. "+ Hisse Ekle" ile başla.</div>
      ) : (
        <>
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs text-gray-500">{visibleHoldings.length} pozisyon</span>
          <ListFilters market={marketFilter} setMarket={setMarketFilter} sector={sectorFilter} setSector={setSectorFilter} sectors={sectors} />
        </div>
        <div className="overflow-x-auto border border-gray-800 rounded-lg">
          <table className="w-full text-sm">
            <thead className="bg-gray-900 text-gray-500">
              <tr>
                <th className="text-left px-3 py-2">Hisse</th>
                <th className="text-left px-3 py-2 hidden lg:table-cell">Sektör</th>
                <th className="text-right px-3 py-2">Adet</th>
                <th className="text-right px-3 py-2 hidden sm:table-cell">Maliyet</th>
                <th className="text-right px-3 py-2">Fiyat</th>
                <th className="text-right px-3 py-2">Değer</th>
                <th className="text-right px-3 py-2">K/Z</th>
                <th className="text-right px-3 py-2 hidden md:table-cell">Ağırlık</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {visibleHoldings.map((h) => (
                <tr key={h.id} className="border-t border-gray-800 hover:bg-gray-800/30">
                  <td className="px-3 py-2 font-mono font-bold text-white cursor-pointer hover:text-blue-400" onClick={() => setReportTicker(h.ticker)}>
                    {h.market === 'us' ? '🇺🇸' : '🇹🇷'} {h.symbol} 📊
                  </td>
                  <td className="px-3 py-2 hidden lg:table-cell text-gray-400 text-xs max-w-[150px] truncate">{h.sector || '—'}</td>
                  <td className="px-3 py-2 text-right font-mono text-gray-300">{fmt(h.shares, 0)}</td>
                  <td className="px-3 py-2 text-right font-mono text-gray-400 hidden sm:table-cell">{h.currency}{fmt(h.cost_basis)}</td>
                  <td className="px-3 py-2 text-right font-mono text-gray-300">{h.price == null ? '—' : `${h.currency}${fmt(h.price)}`}</td>
                  <td className="px-3 py-2 text-right font-mono text-white">{h.market_value == null ? '—' : `${h.currency}${fmt(h.market_value)}`}</td>
                  <td className={`px-3 py-2 text-right font-mono font-bold ${(h.pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {h.pnl == null ? '—' : `${h.pnl >= 0 ? '+' : ''}${fmt(h.pnl)} (${h.pnl_pct >= 0 ? '+' : ''}${fmt(h.pnl_pct)}%)`}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-gray-400 hidden md:table-cell">{h.weight == null ? '—' : `${fmt(h.weight, 1)}%`}</td>
                  <td className="px-3 py-2 text-right">
                    <button onClick={() => removeHolding(h.id)} className="text-red-400 hover:text-red-300 text-xs">Sil</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        </>
      )}

      {reportTicker && (
        <StockReportModal ticker={reportTicker} onClose={() => setReportTicker(null)} />
      )}
    </div>
  );
}
