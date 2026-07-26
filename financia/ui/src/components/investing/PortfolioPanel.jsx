import { useEffect, useState } from 'react';
import { useToast } from '../../contexts/ToastContext';
import StockReportModal from './StockReportModal';
import DiversificationCard from './DiversificationCard';
import ListFilters, { uniqueSectors, specificSector, SearchBox } from './ListFilters';
import AnalyzeButton from './AnalyzeButton';

const API_BASE = import.meta.env.VITE_API_BASE || '';

const fmt = (v, d = 2) => (v == null ? '—' : Number(v).toLocaleString('tr-TR', { minimumFractionDigits: d, maximumFractionDigits: d }));

const emptyForm = { ticker: '', market: 'bist', shares: '', cost_basis: '', purchase_date: '', notes: '' };

export default function PortfolioPanel() {
  const { addToast } = useToast();
  const [data, setData] = useState({ holdings: [], totals: [], summary: [] });
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [reportTicker, setReportTicker] = useState(null);
  const [sellHolding, setSellHolding] = useState(null);
  const [sellShares, setSellShares] = useState('');
  const [sellPrice, setSellPrice] = useState('');
  const [sellNotes, setSellNotes] = useState('');
  const [dividendHolding, setDividendHolding] = useState(null);
  const [dividendAmount, setDividendAmount] = useState('');
  const [marketFilter, setMarketFilter] = useState('all');
  const [sectorFilter, setSectorFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [sortBy, setSortBy] = useState(null); // null = eklenme sırası

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
        const body = await res.json();
        addToast(body.merged ? `${ticker} alışa eklendi, ortalama maliyet güncellendi` : `${ticker} eklendi`, 'success');
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

  const openSell = (holding) => {
    setSellHolding(holding);
    setSellShares('');
    setSellPrice(holding.price == null ? '' : String(holding.price));
    setSellNotes('');
  };

  const sell = async (e) => {
    e.preventDefault();
    const shares = parseFloat(sellShares);
    if (!sellHolding || !Number.isFinite(shares) || shares <= 0) {
      addToast('Geçerli bir satış adedi gir', 'error');
      return;
    }
    if (shares > sellHolding.shares) {
      addToast('Satış adedi mevcut adetten fazla olamaz', 'error');
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/investing/holdings/${sellHolding.id}/sell`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          shares,
          sale_price: sellPrice ? parseFloat(sellPrice) : null,
          sale_date: new Date().toISOString().slice(0, 10),
          notes: sellNotes,
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        addToast(body.detail || 'Satış kaydedilemedi', 'error');
        return;
      }
      addToast(body.fully_sold
        ? `${sellHolding.symbol}: pozisyon tamamen kapatıldı`
        : `${sellHolding.symbol}: ${fmt(shares, 4)} adet satıldı, kalan ${fmt(body.remaining_shares, 4)}`,
      'success');
      setSellHolding(null);
      load();
    } catch {
      addToast('Satış kaydedilemedi', 'error');
    }
  };

  const openDividend = (holding) => {
    setDividendHolding(holding);
    setDividendAmount('');
  };

  const addDividend = async (e) => {
    e.preventDefault();
    const amount = parseFloat(dividendAmount);
    if (!dividendHolding || !Number.isFinite(amount) || amount <= 0) {
      addToast('Geçerli bir temettü tutarı gir', 'error');
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/investing/holdings/${dividendHolding.id}/dividend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        addToast(body.detail || 'Temettü kaydedilemedi', 'error');
        return;
      }
      addToast(`${dividendHolding.symbol}: temettü eklendi`, 'success');
      setDividendHolding(null);
      load();
    } catch {
      addToast('Temettü kaydedilemedi', 'error');
    }
  };

  const sectors = uniqueSectors(data.holdings, specificSector);
  const q = query.trim().toLowerCase();
  const filteredHoldings = data.holdings.filter(
    (h) =>
      (marketFilter === 'all' || h.market === marketFilter) &&
      (sectorFilter === 'all' || specificSector(h) === sectorFilter) &&
      (!q || (h.symbol || '').toLowerCase().includes(q) || specificSector(h).toLowerCase().includes(q))
  );
  const visibleHoldings = sortBy
    ? [...filteredHoldings].sort((a, b) => (b[sortBy] ?? -Infinity) - (a[sortBy] ?? -Infinity))
    : filteredHoldings;

  const scoreColor = (s) =>
    s == null ? 'text-gray-500' : s >= 70 ? 'text-green-400' : s >= 50 ? 'text-blue-400' : s >= 30 ? 'text-yellow-400' : 'text-red-400';
  const SortBtn = ({ field, children }) => (
    <button onClick={() => setSortBy((cur) => (cur === field ? null : field))} className={`hover:text-white ${sortBy === field ? 'text-white' : ''}`}>
      {children}{sortBy === field ? ' ▼' : ''}
    </button>
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

      {data.summary?.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 mb-4">
          {data.summary.map((s) => (
            <div key={s.currency} className="bg-gray-900 border border-gray-800 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-2">Portföy Özeti ({s.currency})</div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                <span className="text-gray-500">Güncel K/Z</span>
                <span className={`text-right font-mono font-bold ${(s.pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {s.pnl == null ? '—' : `${s.pnl >= 0 ? '+' : ''}${s.currency}${fmt(s.pnl)}`}
                </span>
                <span className="text-gray-500">Temettü</span>
                <span className="text-right font-mono font-bold text-yellow-400">{s.currency}{fmt(s.dividends)}</span>
                <span className="text-gray-500">Toplam getiri</span>
                <span className={`text-right font-mono font-bold ${(s.total_return ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {s.total_return == null ? '—' : `${s.total_return >= 0 ? '+' : ''}${s.currency}${fmt(s.total_return)}`}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

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
        <div className="flex items-center gap-2 mb-2 flex-wrap">
          <span className="text-xs text-gray-500">{visibleHoldings.length} pozisyon</span>
          <SearchBox value={query} onChange={setQuery} />
          <ListFilters market={marketFilter} setMarket={setMarketFilter} sector={sectorFilter} setSector={setSectorFilter} sectors={sectors} />
          <AnalyzeButton
            getBody={() => (data.holdings.length ? { tickers: data.holdings.map((h) => h.ticker) } : null)}
            label="🔄 Portföyü Analiz Et"
            onDone={load}
            className="px-3 py-1.5 bg-green-600 hover:bg-green-500 disabled:bg-gray-700 text-white rounded text-xs font-bold transition-colors"
          />
        </div>
        {visibleHoldings.length === 0 ? (
          <div className="text-gray-500 text-center py-12 border border-dashed border-gray-800 rounded-lg">Bu filtreye uyan pozisyon yok.</div>
        ) : (
        <div className="overflow-x-auto border border-gray-800 rounded-lg">
          <table className="w-full text-sm">
            <thead className="bg-gray-900 text-gray-500">
              <tr>
                <th className="text-left px-3 py-2">Hisse</th>
                <th className="text-left px-3 py-2 hidden lg:table-cell">Sektör / Endüstri</th>
                <th className="text-right px-3 py-2">Adet</th>
                <th className="text-right px-3 py-2 hidden sm:table-cell">Maliyet</th>
                <th className="text-right px-3 py-2">Fiyat</th>
                <th className="text-right px-3 py-2"><SortBtn field="market_value">Değer</SortBtn></th>
                <th className="text-right px-3 py-2"><SortBtn field="pnl_pct">K/Z</SortBtn></th>
                <th className="text-right px-3 py-2 hidden md:table-cell"><SortBtn field="weight">Ağırlık</SortBtn></th>
                <th className="text-right px-3 py-2 hidden lg:table-cell"><SortBtn field="dividend_score">Temettü</SortBtn></th>
                <th className="text-right px-3 py-2 hidden lg:table-cell"><SortBtn field="growth_score">Büyüme</SortBtn></th>
                <th className="text-right px-3 py-2 hidden md:table-cell"><SortBtn field="overall_score">Genel</SortBtn></th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {visibleHoldings.map((h) => (
                <tr key={h.id} className="border-t border-gray-800 hover:bg-gray-800/30">
                  <td className="px-3 py-2 font-mono font-bold text-white cursor-pointer hover:text-blue-400" onClick={() => setReportTicker(h.ticker)}>
                    {h.market === 'us' ? '🇺🇸' : '🇹🇷'} {h.symbol} 📊
                  </td>
                  <td className="px-3 py-2 hidden lg:table-cell text-gray-400 text-xs max-w-[150px] truncate" title={h.sector || ''}>{specificSector(h) || '—'}</td>
                  <td className="px-3 py-2 text-right font-mono text-gray-300">{fmt(h.shares, 0)}</td>
                  <td className="px-3 py-2 text-right font-mono text-gray-400 hidden sm:table-cell">{h.currency}{fmt(h.cost_basis)}</td>
                  <td className="px-3 py-2 text-right font-mono text-gray-300">{h.price == null ? '—' : `${h.currency}${fmt(h.price)}`}</td>
                  <td className="px-3 py-2 text-right font-mono text-white">{h.market_value == null ? '—' : `${h.currency}${fmt(h.market_value)}`}</td>
                  <td className={`px-3 py-2 text-right font-mono font-bold ${(h.pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {h.pnl == null ? '—' : `${h.pnl >= 0 ? '+' : ''}${fmt(h.pnl)} (${h.pnl_pct >= 0 ? '+' : ''}${fmt(h.pnl_pct)}%)`}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-gray-400 hidden md:table-cell">{h.weight == null ? '—' : `${fmt(h.weight, 1)}%`}</td>
                  <td className={`px-3 py-2 text-right font-mono font-bold hidden lg:table-cell ${scoreColor(h.dividend_score)}`}>{h.dividend_score == null ? '—' : Math.round(h.dividend_score)}</td>
                  <td className={`px-3 py-2 text-right font-mono font-bold hidden lg:table-cell ${scoreColor(h.growth_score)}`}>{h.growth_score == null ? '—' : Math.round(h.growth_score)}</td>
                  <td className={`px-3 py-2 text-right font-mono font-extrabold hidden md:table-cell ${scoreColor(h.overall_score)}`}>{h.overall_score == null ? '—' : Math.round(h.overall_score)}</td>
                  <td className="px-3 py-2 text-right">
                    <div className="flex justify-end gap-2">
                      <button onClick={() => openDividend(h)} className="text-yellow-400 hover:text-yellow-300 text-xs font-bold" title="Temettü ekle">Tem.</button>
                      <button onClick={() => openSell(h)} className="text-orange-400 hover:text-orange-300 text-xs font-bold">Sat</button>
                      <button onClick={() => removeHolding(h.id)} className="text-red-400 hover:text-red-300 text-xs">Sil</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        )}
        </>
      )}

      {reportTicker && (
        <StockReportModal ticker={reportTicker} onClose={() => setReportTicker(null)} />
      )}

      {sellHolding && (
        <div className="fixed inset-0 z-[60] bg-black/70 flex items-center justify-center p-4" onClick={() => setSellHolding(null)}>
          <form onSubmit={sell} onClick={(e) => e.stopPropagation()} className="w-full max-w-md bg-gray-900 border border-gray-700 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-white">📤 Kademeli Satış — {sellHolding.symbol}</h3>
                <p className="text-xs text-gray-500 mt-1">Mevcut adet: {fmt(sellHolding.shares, 4)}</p>
              </div>
              <button type="button" onClick={() => setSellHolding(null)} className="text-gray-400 hover:text-white text-xl">✕</button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Satılacak adet</label>
                <input type="number" min="0" max={sellHolding.shares} step="any" autoFocus value={sellShares} onChange={(e) => setSellShares(e.target.value)} className="w-full bg-gray-800 border border-gray-700 text-white px-2 py-2 rounded text-sm font-mono" placeholder="Örn. 25" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Satış fiyatı ({sellHolding.currency})</label>
                <input type="number" min="0" step="any" value={sellPrice} onChange={(e) => setSellPrice(e.target.value)} className="w-full bg-gray-800 border border-gray-700 text-white px-2 py-2 rounded text-sm font-mono" placeholder="İsteğe bağlı" />
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Not (isteğe bağlı)</label>
              <input value={sellNotes} onChange={(e) => setSellNotes(e.target.value)} className="w-full bg-gray-800 border border-gray-700 text-white px-2 py-2 rounded text-sm" placeholder="Örn. %25 kâr realizasyonu" />
            </div>
            <p className="text-[11px] text-gray-500">Kalan hisselerin ortalama maliyeti değişmez. Tümünü satarsan pozisyon portföyden kaldırılır.</p>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setSellHolding(null)} className="px-3 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded text-sm">İptal</button>
              <button type="submit" className="px-3 py-2 bg-orange-600 hover:bg-orange-500 text-white rounded text-sm font-bold">Satışı Kaydet</button>
            </div>
          </form>
        </div>
      )}

      {dividendHolding && (
        <div className="fixed inset-0 z-[60] bg-black/70 flex items-center justify-center p-4" onClick={() => setDividendHolding(null)}>
          <form onSubmit={addDividend} onClick={(e) => e.stopPropagation()} className="w-full max-w-sm bg-gray-900 border border-gray-700 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-white">💰 Temettü Ekle — {dividendHolding.symbol}</h3>
              <button type="button" onClick={() => setDividendHolding(null)} className="text-gray-400 hover:text-white text-xl">✕</button>
            </div>
            <p className="text-xs text-gray-500">Bu pozisyon açık kaldığı sürece portföy toplamına dahil edilir.</p>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Alınan temettü ({dividendHolding.currency})</label>
              <input type="number" min="0" step="any" autoFocus value={dividendAmount} onChange={(e) => setDividendAmount(e.target.value)} className="w-full bg-gray-800 border border-gray-700 text-white px-2 py-2 rounded text-sm font-mono" placeholder="Örn. 1250" />
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setDividendHolding(null)} className="px-3 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded text-sm">İptal</button>
              <button type="submit" className="px-3 py-2 bg-yellow-600 hover:bg-yellow-500 text-white rounded text-sm font-bold">Temettüyü Ekle</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
