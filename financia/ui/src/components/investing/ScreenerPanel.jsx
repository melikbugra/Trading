import { useEffect, useRef, useState } from 'react';
import { useToast } from '../../contexts/ToastContext';
import { useWebSocket } from '../../contexts/WebSocketContext';
import StockReportModal from './StockReportModal';
import ListFilters, { uniqueSectors } from './ListFilters';

const API_BASE = import.meta.env.VITE_API_BASE || '';

const scoreColor = (s) =>
  s == null ? 'text-gray-500' : s >= 70 ? 'text-green-400' : s >= 50 ? 'text-blue-400' : s >= 30 ? 'text-yellow-400' : 'text-red-400';

const LABEL_BADGE = {
  'temettü': 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
  'büyüme': 'bg-green-500/20 text-green-300 border-green-500/40',
  'ikisi': 'bg-blue-500/20 text-blue-300 border-blue-500/40',
  'zayıf': 'bg-gray-600/30 text-gray-400 border-gray-600/50',
};

const fmt = (v, d = 2) => (v == null ? '—' : Number(v).toLocaleString('tr-TR', { maximumFractionDigits: d }));

export default function ScreenerPanel() {
  const { addToast } = useToast();
  const { investingScanProgress } = useWebSocket();
  const [results, setResults] = useState([]);
  const [scanning, setScanning] = useState(false);
  const [sortBy, setSortBy] = useState('overall_score');
  const [reportTicker, setReportTicker] = useState(null);
  const [reportMarket, setReportMarket] = useState(null);
  const [singleTicker, setSingleTicker] = useState('');
  const [singleMarket, setSingleMarket] = useState('bist');
  const [sectorFilter, setSectorFilter] = useState('all');
  const [marketFilter, setMarketFilter] = useState('all');
  const lastDoneRef = useRef(null);

  const openReport = (ticker, market) => {
    setReportTicker(ticker);
    setReportMarket(market || null);
  };

  const loadScreener = async () => {
    try {
      const res = await fetch(`${API_BASE}/investing/screener`);
      const data = await res.json();
      setResults(data.results || []);
    } catch { /* ignore */ }
  };

  useEffect(() => { loadScreener(); }, []);

  // React to live scan progress broadcast over the websocket.
  useEffect(() => {
    const p = investingScanProgress;
    if (!p) return;
    if (p.status === 'started' || p.status === 'running') {
      setScanning(true);
    } else if (p.status === 'completed') {
      // guard against double-handling the same completion
      const key = `${p.label}-${p.total}-${p.count}`;
      if (lastDoneRef.current !== key) {
        lastDoneRef.current = key;
        setScanning(false);
        loadScreener();
        const skipped = p.skipped?.length || 0;
        addToast(
          `${p.label}: ${p.count} hisse skorlandı` +
          (skipped ? `, ${skipped} atlandı (veri yok/delisted)` : '') +
          (p.errors ? `, ${p.errors} hata` : ''),
          'success', 6000,
        );
      }
    }
    // eslint-disable-next-line
  }, [investingScanProgress]);

  const runScan = async (body, label) => {
    setScanning(true);
    try {
      const res = await fetch(`${API_BASE}/investing/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const data = await res.json();
        addToast(`${label} taranıyor… ${data.total} hisse (arka planda, ilerleme aşağıda)`, 'info', 4000);
      } else if (res.status === 409) {
        addToast('Zaten bir tarama çalışıyor', 'error');
        setScanning(false);
      } else {
        addToast('Tarama başlatılamadı', 'error');
        setScanning(false);
      }
    } catch {
      addToast('Tarama başlatılamadı', 'error');
      setScanning(false);
    }
  };

  const sectors = uniqueSectors(results, (r) => r.sector);
  const filtered = results.filter(
    (r) => (marketFilter === 'all' || r.market === marketFilter) && (sectorFilter === 'all' || r.sector === sectorFilter)
  );
  const sorted = [...filtered].sort((a, b) => (b[sortBy] ?? -1) - (a[sortBy] ?? -1));

  const SortBtn = ({ field, children }) => (
    <button onClick={() => setSortBy(field)} className={`hover:text-white ${sortBy === field ? 'text-white' : ''}`}>
      {children}{sortBy === field ? ' ▼' : ''}
    </button>
  );

  const analyzeSingle = (e) => {
    e.preventDefault();
    const t = singleTicker.trim().toUpperCase();
    if (t) openReport(t, singleMarket); // backend appends .IS for BIST
  };

  const deleteOne = async (ticker, e) => {
    e.stopPropagation();
    setResults((prev) => prev.filter((r) => r.ticker !== ticker)); // optimistic
    try {
      await fetch(`${API_BASE}/investing/screener/${encodeURIComponent(ticker)}`, { method: 'DELETE' });
    } catch {
      addToast('Silinemedi', 'error');
      loadScreener();
    }
  };

  const clearAll = async () => {
    if (!results.length) return;
    if (!window.confirm(`Tarayıcıdaki ${results.length} hissenin tümü silinsin mi?`)) return;
    try {
      await fetch(`${API_BASE}/investing/screener`, { method: 'DELETE' });
      setResults([]);
      addToast('Tarayıcı listesi temizlendi', 'success');
    } catch {
      addToast('Silinemedi', 'error');
    }
  };

  return (
    <div>
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <button
          onClick={() => runScan({ market: 'bist' }, 'BIST 100')}
          disabled={scanning}
          className="px-3 py-2 bg-red-600 hover:bg-red-500 disabled:bg-gray-700 text-white rounded text-sm font-bold transition-colors"
        >
          🇹🇷 BIST 100 Tara
        </button>
        <button
          onClick={() => runScan({ market: 'us' }, 'S&P 100')}
          disabled={scanning}
          className="px-3 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white rounded text-sm font-bold transition-colors"
        >
          🇺🇸 S&P 100 Tara
        </button>
        <button
          onClick={() => runScan({ use_watchlist: true }, 'İzleme listesi')}
          disabled={scanning}
          className="px-3 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-700 text-white rounded text-sm font-bold transition-colors"
        >
          ⭐ İzleme Listesini Tara
        </button>
        <form onSubmit={analyzeSingle} className="ml-auto flex gap-2">
          <select
            value={singleMarket}
            onChange={(e) => setSingleMarket(e.target.value)}
            className="bg-gray-800 border border-gray-700 text-white px-2 py-2 rounded text-sm"
          >
            <option value="bist">🇹🇷 TR</option>
            <option value="us">🇺🇸 US</option>
          </select>
          <input
            value={singleTicker}
            onChange={(e) => setSingleTicker(e.target.value)}
            placeholder={singleMarket === 'bist' ? 'THYAO' : 'AAPL'}
            className="bg-gray-800 border border-gray-700 text-white px-3 py-2 rounded text-sm font-mono uppercase w-36"
          />
          <button type="submit" className="px-3 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded text-sm font-bold">Analiz</button>
        </form>
      </div>

      {/* Live progress */}
      {scanning && investingScanProgress && investingScanProgress.status !== 'completed' && (
        <div className="mb-3 bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
            <span className="animate-pulse">
              {investingScanProgress.label} taranıyor… {investingScanProgress.ticker || ''}
            </span>
            <span className="font-mono">{investingScanProgress.current}/{investingScanProgress.total}</span>
          </div>
          <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 transition-all"
              style={{ width: `${investingScanProgress.total ? (investingScanProgress.current / investingScanProgress.total * 100) : 0}%` }}
            />
          </div>
        </div>
      )}

      <p className="text-xs text-gray-500 mb-3">
        Tarama yfinance'tan temel verileri çeker — full pazar taraması birkaç dakika sürebilir (manuel, otomatik değil).
        BIST'te bazı kalemler eksik olabilir; bir hisseye tıklayıp raporda elle düzeltebilirsin.
      </p>

      {/* Results table */}
      {sorted.length === 0 ? (
        <div className="text-gray-500 text-center py-16 border border-dashed border-gray-800 rounded-lg">
          Henüz sonuç yok. Bir pazar tara ya da tek hisse analiz et.
        </div>
      ) : (
        <>
        <div className="flex items-center justify-between mb-2 gap-2">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">{sorted.length} hisse</span>
            <ListFilters market={marketFilter} setMarket={setMarketFilter} sector={sectorFilter} setSector={setSectorFilter} sectors={sectors} />
          </div>
          <button
            onClick={clearAll}
            className="text-xs text-red-400 hover:text-red-300 border border-red-500/30 hover:border-red-500/60 rounded px-2 py-1 transition-colors"
          >
            🗑 Tümünü Sil
          </button>
        </div>
        <div className="overflow-x-auto border border-gray-800 rounded-lg">
          <table className="w-full text-sm">
            <thead className="bg-gray-900 text-gray-500">
              <tr>
                <th className="text-left px-3 py-2">Hisse</th>
                <th className="text-left px-3 py-2 hidden lg:table-cell">Sektör</th>
                <th className="text-left px-3 py-2 hidden sm:table-cell">Etiket</th>
                <th className="text-right px-3 py-2"><SortBtn field="dividend_yield">Tem.%</SortBtn></th>
                <th className="text-right px-3 py-2 hidden sm:table-cell">F/K</th>
                <th className="text-right px-3 py-2 hidden md:table-cell">ROE%</th>
                <th className="text-right px-3 py-2"><SortBtn field="dividend_score">Temettü</SortBtn></th>
                <th className="text-right px-3 py-2"><SortBtn field="growth_score">Büyüme</SortBtn></th>
                <th className="text-right px-3 py-2"><SortBtn field="value_score">Değer</SortBtn></th>
                <th className="text-right px-3 py-2"><SortBtn field="overall_score">Genel</SortBtn></th>
                <th className="px-2 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr
                  key={r.ticker}
                  onClick={() => openReport(r.ticker, r.market)}
                  className="border-t border-gray-800 hover:bg-gray-800/40 cursor-pointer"
                >
                  <td className="px-3 py-2 font-mono font-bold text-white">
                    {r.market === 'us' ? '🇺🇸' : '🇹🇷'} {r.symbol}
                  </td>
                  <td className="px-3 py-2 hidden lg:table-cell text-gray-400 text-xs max-w-[160px] truncate" title={r.industry || ''}>
                    {r.sector || '—'}
                  </td>
                  <td className="px-3 py-2 hidden sm:table-cell">
                    {r.label && <span className={`px-2 py-0.5 rounded text-xs font-bold border ${LABEL_BADGE[r.label] || ''}`}>{r.label}</span>}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-gray-300">{fmt(r.dividend_yield)}</td>
                  <td className="px-3 py-2 text-right font-mono text-gray-300 hidden sm:table-cell">{fmt(r.trailing_pe)}</td>
                  <td className="px-3 py-2 text-right font-mono text-gray-300 hidden md:table-cell">{fmt(r.roe)}</td>
                  <td className={`px-3 py-2 text-right font-mono font-bold ${scoreColor(r.dividend_score)}`}>{r.dividend_score == null ? '—' : Math.round(r.dividend_score)}</td>
                  <td className={`px-3 py-2 text-right font-mono font-bold ${scoreColor(r.growth_score)}`}>{r.growth_score == null ? '—' : Math.round(r.growth_score)}</td>
                  <td className={`px-3 py-2 text-right font-mono font-bold ${scoreColor(r.value_score)}`} title="Sektör emsallerine göre ucuzluk">{r.value_score == null ? '—' : Math.round(r.value_score)}</td>
                  <td className={`px-3 py-2 text-right font-mono font-extrabold ${scoreColor(r.overall_score)}`}>{r.overall_score == null ? '—' : Math.round(r.overall_score)}</td>
                  <td className="px-2 py-2 text-right">
                    <button
                      onClick={(e) => deleteOne(r.ticker, e)}
                      className="text-gray-600 hover:text-red-400 transition-colors"
                      title="Listeden sil"
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        </>
      )}

      {reportTicker && (
        <StockReportModal
          ticker={reportTicker}
          market={reportMarket}
          onClose={() => { setReportTicker(null); loadScreener(); }}
        />
      )}
    </div>
  );
}
