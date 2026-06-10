import { useEffect, useState } from 'react';
import { useToast } from '../../contexts/ToastContext';
import StockReportModal from './StockReportModal';
import ListFilters, { uniqueSectors, SearchBox } from './ListFilters';
import AnalyzeButton from './AnalyzeButton';

const API_BASE = import.meta.env.VITE_API_BASE || '';

const scoreColor = (s) =>
  s == null ? 'text-gray-500' : s >= 70 ? 'text-green-400' : s >= 50 ? 'text-blue-400' : s >= 30 ? 'text-yellow-400' : 'text-red-400';

export default function WatchlistPanel() {
  const { addToast } = useToast();
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ ticker: '', market: 'bist' });
  const [reportTicker, setReportTicker] = useState(null);
  const [marketFilter, setMarketFilter] = useState('all');
  const [sectorFilter, setSectorFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [sortBy, setSortBy] = useState(null); // null = eklenme sırası

  const load = async () => {
    try {
      const res = await fetch(`${API_BASE}/investing/watchlist`);
      const data = await res.json();
      setItems(data.watchlist || []);
    } catch { /* ignore */ }
  };

  useEffect(() => { load(); }, []);

  const add = async (e) => {
    e.preventDefault();
    if (!form.ticker) return;
    let ticker = form.ticker.trim().toUpperCase();
    if (form.market === 'bist' && !ticker.endsWith('.IS')) ticker += '.IS';
    try {
      const res = await fetch(`${API_BASE}/investing/watchlist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker, market: form.market }),
      });
      if (res.ok) {
        setForm({ ticker: '', market: form.market });
        load();
      } else {
        const d = await res.json();
        addToast(d.detail || 'Eklenemedi', 'error');
      }
    } catch { addToast('Eklenemedi', 'error'); }
  };

  const remove = async (id) => {
    await fetch(`${API_BASE}/investing/watchlist/${id}`, { method: 'DELETE' });
    load();
  };

  const sectors = uniqueSectors(items, (it) => it.scores?.sector);
  const q = query.trim().toLowerCase();
  const filtered = items.filter(
    (it) =>
      (marketFilter === 'all' || it.market === marketFilter) &&
      (sectorFilter === 'all' || it.scores?.sector === sectorFilter) &&
      (!q || (it.symbol || '').toLowerCase().includes(q) || (it.scores?.sector || '').toLowerCase().includes(q))
  );
  const sorted = sortBy
    ? [...filtered].sort((a, b) => (b.scores?.[sortBy] ?? -1) - (a.scores?.[sortBy] ?? -1))
    : filtered;

  const SortBtn = ({ field, children }) => (
    <button onClick={() => setSortBy((cur) => (cur === field ? null : field))} className={`hover:text-white ${sortBy === field ? 'text-white' : ''}`}>
      {children}{sortBy === field ? ' ▼' : ''}
    </button>
  );

  return (
    <div>
      <form onSubmit={add} className="flex flex-wrap gap-2 mb-4">
        <select value={form.market} onChange={(e) => setForm({ ...form, market: e.target.value })} className="bg-gray-800 border border-gray-700 text-white px-2 py-2 rounded text-sm">
          <option value="bist">🇹🇷 BIST</option>
          <option value="us">🇺🇸 ABD</option>
        </select>
        <input value={form.ticker} onChange={(e) => setForm({ ...form, ticker: e.target.value })} placeholder={form.market === 'bist' ? 'THYAO' : 'AAPL'} className="bg-gray-800 border border-gray-700 text-white px-3 py-2 rounded text-sm font-mono uppercase w-40" />
        <button type="submit" className="px-3 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded text-sm font-bold">+ İzlemeye Ekle</button>
        <span className="text-xs text-gray-500 self-center">Skorlar "Analiz & Tarayıcı → İzleme Listesini Tara" ile doldurulur.</span>
      </form>

      {items.length === 0 ? (
        <div className="text-gray-500 text-center py-16 border border-dashed border-gray-800 rounded-lg">İzleme listen boş.</div>
      ) : (
        <>
        <div className="flex items-center gap-2 mb-2 flex-wrap">
          <span className="text-xs text-gray-500">{filtered.length} hisse</span>
          <SearchBox value={query} onChange={setQuery} />
          <ListFilters market={marketFilter} setMarket={setMarketFilter} sector={sectorFilter} setSector={setSectorFilter} sectors={sectors} />
          <AnalyzeButton
            getBody={() => ({ use_watchlist: true })}
            label="🔄 Listeyi Analiz Et"
            onDone={load}
            className="px-3 py-1.5 bg-green-600 hover:bg-green-500 disabled:bg-gray-700 text-white rounded text-xs font-bold transition-colors"
          />
        </div>
        {filtered.length === 0 ? (
          <div className="text-gray-500 text-center py-12 border border-dashed border-gray-800 rounded-lg">Bu filtreye uyan hisse yok.</div>
        ) : (
        <div className="overflow-x-auto border border-gray-800 rounded-lg">
          <table className="w-full text-sm">
            <thead className="bg-gray-900 text-gray-500">
              <tr>
                <th className="text-left px-3 py-2">Hisse</th>
                <th className="text-left px-3 py-2 hidden lg:table-cell">Sektör</th>
                <th className="text-left px-3 py-2 hidden sm:table-cell">Etiket</th>
                <th className="text-right px-3 py-2"><SortBtn field="dividend_score">Temettü</SortBtn></th>
                <th className="text-right px-3 py-2"><SortBtn field="growth_score">Büyüme</SortBtn></th>
                <th className="text-right px-3 py-2"><SortBtn field="overall_score">Genel</SortBtn></th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((it) => {
                const s = it.scores;
                return (
                  <tr key={it.id} className="border-t border-gray-800 hover:bg-gray-800/30">
                    <td className="px-3 py-2 font-mono font-bold text-white cursor-pointer hover:text-blue-400" onClick={() => setReportTicker(it.ticker)}>
                      {it.market === 'us' ? '🇺🇸' : '🇹🇷'} {it.symbol} 📊
                    </td>
                    <td className="px-3 py-2 hidden lg:table-cell text-gray-400 text-xs max-w-[150px] truncate">{s?.sector || '—'}</td>
                    <td className="px-3 py-2 hidden sm:table-cell text-gray-400 text-xs">{s?.label || '—'}</td>
                    <td className={`px-3 py-2 text-right font-mono font-bold ${scoreColor(s?.dividend_score)}`}>{s?.dividend_score == null ? '—' : Math.round(s.dividend_score)}</td>
                    <td className={`px-3 py-2 text-right font-mono font-bold ${scoreColor(s?.growth_score)}`}>{s?.growth_score == null ? '—' : Math.round(s.growth_score)}</td>
                    <td className={`px-3 py-2 text-right font-mono font-extrabold ${scoreColor(s?.overall_score)}`}>{s?.overall_score == null ? '—' : Math.round(s.overall_score)}</td>
                    <td className="px-3 py-2 text-right"><button onClick={() => remove(it.id)} className="text-red-400 hover:text-red-300 text-xs">Sil</button></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        )}
        </>
      )}

      {reportTicker && <StockReportModal ticker={reportTicker} onClose={() => { setReportTicker(null); load(); }} />}
    </div>
  );
}
