import { useEffect, useState } from 'react';
import ListFilters, { uniqueSectors } from './ListFilters';

const API_BASE = import.meta.env.VITE_API_BASE || '';

const fmt = (v, d = 2) => (v == null ? '—' : Number(v).toLocaleString('tr-TR', { minimumFractionDigits: d, maximumFractionDigits: d }));

export default function DividendCalendarPanel() {
  const [data, setData] = useState({ holdings: [], projected_annual_income: [] });
  const [loading, setLoading] = useState(true);
  const [marketFilter, setMarketFilter] = useState('all');
  const [sectorFilter, setSectorFilter] = useState('all');

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/investing/dividends/calendar`);
      setData(await res.json());
    } catch { /* ignore */ } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const needsScan = data.holdings?.some((h) => !h.has_snapshot);
  const sectors = uniqueSectors(data.holdings, (h) => h.sector);
  const filtered = data.holdings.filter(
    (h) => (marketFilter === 'all' || h.market === marketFilter) && (sectorFilter === 'all' || h.sector === sectorFilter)
  );

  return (
    <div>
      {/* Projected income */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        {data.projected_annual_income?.length > 0 ? data.projected_annual_income.map((t) => (
          <div key={t.currency} className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-2">
            <div className="text-xs text-gray-500">Tahmini Yıllık Temettü ({t.currency})</div>
            <div className="text-lg font-bold text-yellow-400 font-mono">{t.currency}{fmt(t.amount)}</div>
          </div>
        )) : <div className="text-gray-500 text-sm">Tahmin için portföyde temettü verisi olan hisse gerekli.</div>}
        <button onClick={load} className="ml-auto px-3 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded text-sm">↻ Yenile</button>
      </div>

      {needsScan && (
        <p className="text-xs text-yellow-400 mb-3">
          Bazı hisselerin temettü verisi yok — "Analiz & Tarayıcı" sekmesinde tarayarak doldur.
        </p>
      )}

      {loading ? (
        <div className="text-gray-400 text-center py-10">Yükleniyor…</div>
      ) : data.holdings.length === 0 ? (
        <div className="text-gray-500 text-center py-16 border border-dashed border-gray-800 rounded-lg">Portföyünde hisse yok.</div>
      ) : (
        <>
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs text-gray-500">{filtered.length} hisse</span>
          <ListFilters market={marketFilter} setMarket={setMarketFilter} sector={sectorFilter} setSector={setSectorFilter} sectors={sectors} />
        </div>
        <div className="overflow-x-auto border border-gray-800 rounded-lg">
          <table className="w-full text-sm">
            <thead className="bg-gray-900 text-gray-500">
              <tr>
                <th className="text-left px-3 py-2">Hisse</th>
                <th className="text-left px-3 py-2 hidden lg:table-cell">Sektör</th>
                <th className="text-right px-3 py-2">Adet</th>
                <th className="text-right px-3 py-2">Temettü Verimi</th>
                <th className="text-right px-3 py-2">Tahmini Yıllık Gelir</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((h) => (
                <tr key={h.ticker} className="border-t border-gray-800 hover:bg-gray-800/30">
                  <td className="px-3 py-2 font-mono font-bold text-white">{h.market === 'us' ? '🇺🇸' : '🇹🇷'} {h.symbol}</td>
                  <td className="px-3 py-2 hidden lg:table-cell text-gray-400 text-xs max-w-[150px] truncate">{h.sector || '—'}</td>
                  <td className="px-3 py-2 text-right font-mono text-gray-300">{fmt(h.shares, 0)}</td>
                  <td className="px-3 py-2 text-right font-mono text-gray-300">{h.dividend_yield == null ? '—' : `${fmt(h.dividend_yield)}%`}</td>
                  <td className="px-3 py-2 text-right font-mono text-yellow-400 font-bold">{h.annual_income == null ? '—' : `${h.currency}${fmt(h.annual_income)}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        </>
      )}
    </div>
  );
}
