import { useEffect, useState } from 'react';
import { useToast } from '../../contexts/ToastContext';
import { currencySymbol, marketFlag } from '../../utils/market';
import { dateTag } from '../../utils/dates';

const API_BASE = import.meta.env.VITE_API_BASE || '';

// Metric fields the user can override (must match backend OVERRIDABLE_FIELDS).
const METRIC_ROWS = [
  { key: 'dividend_yield', label: 'Temettü Verimi', unit: '%' },
  { key: 'trailing_pe', label: 'F/K (TTM)', unit: '' },
  { key: 'forward_pe', label: 'İleri F/K', unit: '' },
  { key: 'price_to_book', label: 'F/DD (P/B)', unit: '' },
  { key: 'roe', label: 'Özkaynak Kârlılığı (ROE)', unit: '%' },
  { key: 'debt_to_equity', label: 'Borç/Özkaynak', unit: '' },
  { key: 'profit_margin', label: 'Net Kâr Marjı', unit: '%' },
  { key: 'revenue_growth', label: 'Gelir Büyümesi', unit: '%' },
  { key: 'earnings_growth', label: 'Kâr Büyümesi', unit: '%' },
  { key: 'payout_ratio', label: 'Temettü Dağıtım Oranı', unit: '%' },
];

const LABEL_BADGE = {
  'temettü': 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
  'büyüme': 'bg-green-500/20 text-green-300 border-green-500/40',
  'ikisi': 'bg-blue-500/20 text-blue-300 border-blue-500/40',
  'zayıf': 'bg-gray-600/30 text-gray-400 border-gray-600/50',
};

const scoreColor = (s) =>
  s == null ? 'text-gray-500' : s >= 70 ? 'text-green-400' : s >= 50 ? 'text-blue-400' : s >= 30 ? 'text-yellow-400' : 'text-red-400';

const fmt = (v, digits = 2) => (v == null || Number.isNaN(v) ? '—' : Number(v).toLocaleString('tr-TR', { maximumFractionDigits: digits }));

function ScoreGauge({ label, score }) {
  return (
    <div className="bg-gray-800/60 rounded-lg p-3 text-center">
      <div className="text-xs text-gray-400 mb-1">{label}</div>
      <div className={`text-2xl font-extrabold ${scoreColor(score)}`}>{score == null ? '—' : Math.round(score)}</div>
      <div className="h-1.5 bg-gray-700 rounded-full mt-2 overflow-hidden">
        <div
          className={`h-full ${score >= 70 ? 'bg-green-500' : score >= 50 ? 'bg-blue-500' : score >= 30 ? 'bg-yellow-500' : 'bg-red-500'}`}
          style={{ width: `${score || 0}%` }}
        />
      </div>
    </div>
  );
}

const fmtNewsDate = (s) => {
  if (!s) return '';
  try {
    const d = new Date(s);
    return Number.isNaN(d.getTime()) ? s : d.toLocaleString('tr-TR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return s; }
};
const fmtDay = (s) => {
  if (!s) return '—';
  try {
    const d = new Date(s);
    return Number.isNaN(d.getTime()) ? s : d.toLocaleDateString('tr-TR', { day: '2-digit', month: 'short', year: 'numeric' });
  } catch { return s; }
};

function DayTag({ value }) {
  const tag = dateTag(value);
  if (!tag) return null;
  return <span className={`ml-1.5 text-[10px] px-1.5 py-0.5 rounded border ${tag.cls}`}>{tag.text}</span>;
}

function NewsTab({ ticker, market, cur }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let on = true;
    (async () => {
      setLoading(true);
      try {
        const mq = market ? `?market=${encodeURIComponent(market)}` : '';
        const res = await fetch(`${API_BASE}/investing/news/${encodeURIComponent(ticker)}${mq}`);
        const d = await res.json();
        if (on) setData(d);
      } catch {
        if (on) setData({ news: [] });
      } finally {
        if (on) setLoading(false);
      }
    })();
    return () => { on = false; };
  }, [ticker, market]);

  if (loading) return <div className="py-12 text-center text-gray-400">Haberler yükleniyor… <span className="animate-spin inline-block">⏳</span></div>;
  if (!data) return <div className="py-12 text-center text-gray-500">Haber yok.</div>;

  return (
    <div className="space-y-4">
      {/* Upcoming dates */}
      {(data.earnings_date || data.ex_dividend_date || data.dividend_date) && (
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm bg-gray-800/40 rounded-lg p-3">
          {data.earnings_date && <span className="text-gray-400">📅 Bilanço: <span className="text-white">{fmtDay(data.earnings_date)}</span><DayTag value={data.earnings_date} /></span>}
          {data.ex_dividend_date && <span className="text-gray-400">Ex-Temettü: <span className="text-white">{fmtDay(data.ex_dividend_date)}</span><DayTag value={data.ex_dividend_date} /></span>}
          {data.dividend_date && <span className="text-gray-400">Temettü Ödeme: <span className="text-white">{fmtDay(data.dividend_date)}</span><DayTag value={data.dividend_date} /></span>}
        </div>
      )}

      {/* News list */}
      {(!data.news || data.news.length === 0) ? (
        <div className="py-10 text-center text-gray-500">Haber bulunamadı.</div>
      ) : (
        <div className="space-y-2">
          {data.news.map((n, i) => (
            <a
              key={i}
              href={n.link || '#'}
              target="_blank"
              rel="noopener noreferrer"
              className="block bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-lg p-3 transition-colors"
            >
              <div className="text-white text-sm leading-snug">{n.title}</div>
              <div className="text-gray-500 text-xs mt-1">
                {n.publisher || 'Kaynak ?'}{n.published ? ` · ${fmtNewsDate(n.published)}` : ''}
              </div>
            </a>
          ))}
        </div>
      )}
      <p className="text-[11px] text-gray-600">
        {market === 'us' ? 'Kaynak: Yahoo Finance' : 'Kaynak: Google Haberler (Türkçe)'}
      </p>
    </div>
  );
}

function StatementTable({ data }) {
  const rows = Object.keys(data || {});
  if (rows.length === 0) {
    return <div className="text-gray-500 text-sm py-6 text-center">Bu tablo için veri yok (BIST'te eksik olabilir).</div>;
  }
  const years = Object.keys(data[rows[0]] || {});
  const fmtBig = (v) => {
    if (v == null) return '—';
    const abs = Math.abs(v);
    if (abs >= 1e9) return (v / 1e9).toFixed(2) + 'B';
    if (abs >= 1e6) return (v / 1e6).toFixed(2) + 'M';
    if (abs >= 1e3) return (v / 1e3).toFixed(1) + 'K';
    return v.toFixed(0);
  };
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-gray-500 border-b border-gray-700">
            <th className="text-left py-2 pr-2 font-medium sticky left-0 bg-gray-900">Kalem</th>
            {years.map((y) => <th key={y} className="text-right py-2 px-2 font-mono">{y}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r} className="border-b border-gray-800/60">
              <td className="text-left py-1.5 pr-2 text-gray-300 sticky left-0 bg-gray-900 whitespace-nowrap">{r}</td>
              {years.map((y) => <td key={y} className="text-right py-1.5 px-2 font-mono text-gray-400">{fmtBig(data[r][y])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function StockReportModal({ ticker, market, onClose }) {
  const { addToast } = useToast();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('fundamental'); // 'fundamental' | 'news'
  const [stmtTab, setStmtTab] = useState('income');
  const [editing, setEditing] = useState(false);
  const [overrideDraft, setOverrideDraft] = useState({});
  const [saving, setSaving] = useState(false);
  const [adding, setAdding] = useState(false);
  const [showBuy, setShowBuy] = useState(false);
  const [buyShares, setBuyShares] = useState('');
  const [buyCost, setBuyCost] = useState('');

  const mq = market ? `&market=${encodeURIComponent(market)}` : '';

  const load = async (force = true) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/investing/analysis/${encodeURIComponent(ticker)}?force=${force}${mq}`);
      const data = await res.json();
      setReport(data);
      setOverrideDraft(data.overrides || {});
    } catch {
      addToast('Analiz yüklenemedi', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(true); /* eslint-disable-next-line */ }, [ticker]);

  const saveOverrides = async () => {
    setSaving(true);
    try {
      const fields = {};
      Object.entries(overrideDraft).forEach(([k, v]) => {
        if (v !== '' && v != null) fields[k] = parseFloat(v);
      });
      // use the backend-normalized ticker (e.g. THYAO -> THYAO.IS) when available
      const t = report?.ticker || ticker;
      const res = await fetch(`${API_BASE}/investing/overrides/${encodeURIComponent(t)}${market ? `?market=${encodeURIComponent(market)}` : ''}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fields }),
      });
      if (res.ok) {
        const data = await res.json();
        setReport(data);
        setOverrideDraft(data.overrides || {});
        setEditing(false);
        addToast('Düzeltmeler kaydedildi, skorlar güncellendi', 'success');
      } else {
        addToast('Kaydedilemedi', 'error');
      }
    } finally {
      setSaving(false);
    }
  };

  // Backend-normalized ticker/market (e.g. THYAO -> THYAO.IS), once loaded.
  const tkr = report?.ticker || ticker;
  const mkt = report?.market || market;

  const addToWatchlist = async () => {
    setAdding(true);
    try {
      const res = await fetch(`${API_BASE}/investing/watchlist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: tkr, market: mkt }),
      });
      if (res.ok) {
        addToast('İzleme listesine eklendi', 'success');
      } else {
        const d = await res.json().catch(() => ({}));
        addToast(d.detail || 'Eklenemedi', 'error');
      }
    } catch {
      addToast('Eklenemedi', 'error');
    } finally {
      setAdding(false);
    }
  };

  const openBuy = () => {
    setBuyCost(report?.price != null ? String(report.price) : '');
    setShowBuy(true);
  };

  const addToPortfolio = async (e) => {
    e.preventDefault();
    if (!buyShares || !buyCost) {
      addToast('Adet ve maliyet gerekli', 'error');
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/investing/holdings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: tkr,
          market: mkt,
          shares: parseFloat(buyShares),
          cost_basis: parseFloat(buyCost),
        }),
      });
      if (res.ok) {
        addToast('Portföye eklendi', 'success');
        setShowBuy(false);
        setBuyShares('');
      } else {
        addToast('Eklenemedi', 'error');
      }
    } catch {
      addToast('Eklenemedi', 'error');
    }
  };

  const cur = report ? (report.currency || currencySymbol(report.market)) : '';
  const m = report?.metrics || {};
  const overrides = report?.overrides || {};

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-2 sm:p-4" onClick={onClose}>
      <div
        className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-4xl max-h-[92vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-800 sticky top-0 bg-gray-900 z-10">
          <div className="flex items-center gap-2">
            <span>{marketFlag(report?.market)}</span>
            <h2 className="text-lg font-bold text-white">{ticker.replace('.IS', '')}</h2>
            {report?.name && report.name !== ticker && (
              <span className="text-gray-500 text-sm hidden sm:inline truncate max-w-[240px]">{report.name}</span>
            )}
            {report?.label && (
              <span className={`px-2 py-0.5 rounded text-xs font-bold border ${LABEL_BADGE[report.label] || ''}`}>
                {report.label}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => load(true)} className="text-gray-400 hover:text-white text-sm px-2" title="Yenile">↻</button>
            <button onClick={onClose} className="text-red-400 hover:text-red-300 text-xl px-2">✕</button>
          </div>
        </div>

        {loading ? (
          <div className="py-20 text-center text-gray-400">Yükleniyor… <span className="animate-spin inline-block">⏳</span></div>
        ) : !report ? (
          <div className="py-20 text-center text-gray-500">Veri yok.</div>
        ) : (
          <div className="p-4 space-y-5">
            {report.valid === false && (
              <div className="text-red-400 text-sm bg-red-500/10 border border-red-500/30 rounded p-2">
                Bu sembol için veri bulunamadı — borsadan çıkmış (delisted) veya sembol yanlış olabilir.
              </div>
            )}
            {report.error && report.valid !== false && (
              <div className="text-yellow-400 text-xs bg-yellow-500/10 border border-yellow-500/30 rounded p-2">
                Uyarı: bazı veriler çekilemedi ({report.error}).
              </div>
            )}

            {/* Tabs */}
            <div className="flex gap-2 border-b border-gray-800">
              {[['fundamental', '📊 Temel Analiz'], ['news', '📰 Haberler']].map(([k, lbl]) => (
                <button
                  key={k}
                  onClick={() => setTab(k)}
                  className={`px-3 py-2 text-sm font-bold border-b-2 -mb-px transition-colors ${tab === k ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-500 hover:text-gray-300'}`}
                >
                  {lbl}
                </button>
              ))}
            </div>

            {tab === 'news' && <NewsTab ticker={tkr} market={mkt} cur={cur} />}

            {tab === 'fundamental' && (<>
            {/* Scores */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <ScoreGauge label="Temettü Skoru" score={report.dividend_score} />
              <ScoreGauge label="Büyüme Skoru" score={report.growth_score} />
              <ScoreGauge label="Değer Skoru" score={report.value_score} />
              <ScoreGauge label="Genel Skor" score={report.overall_score} />
            </div>
            {report.value_score == null && (
              <p className="text-[11px] text-gray-600 -mt-3">
                Değer skoru için aynı sektörden en az birkaç hisse taranmış olmalı (sektör emsaliyle kıyas).
              </p>
            )}

            {/* Summary header line */}
            <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
              <span className="text-gray-400">Fiyat: <span className="text-white font-mono">{cur}{fmt(report.price)}</span></span>
              <span className="text-gray-400">Piyasa Değeri: <span className="text-white font-mono">{cur}{fmt(report.market_cap, 0)}</span></span>
              {m.sector && (
                <span className="px-2 py-0.5 rounded text-xs font-bold border bg-cyan-500/15 text-cyan-300 border-cyan-500/40">
                  🏭 {m.sector}{m.industry ? ` · ${m.industry}` : ''}
                </span>
              )}
            </div>

            {/* Actions: add to watchlist / portfolio */}
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={addToWatchlist}
                disabled={adding}
                className="px-3 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-700 text-white rounded text-sm font-bold transition-colors"
              >
                ⭐ İzlemeye Ekle
              </button>
              <button
                onClick={openBuy}
                className="px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded text-sm font-bold transition-colors"
              >
                💼 Portföye Ekle
              </button>
            </div>

            {showBuy && (
              <form onSubmit={addToPortfolio} className="flex flex-wrap items-end gap-3 bg-gray-800/40 border border-gray-700 rounded-lg p-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Adet</label>
                  <input
                    type="number" step="any" autoFocus
                    value={buyShares}
                    onChange={(e) => setBuyShares(e.target.value)}
                    className="w-28 bg-gray-900 border border-gray-700 text-white px-2 py-2 rounded text-sm font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Maliyet/Adet ({cur})</label>
                  <input
                    type="number" step="any"
                    value={buyCost}
                    onChange={(e) => setBuyCost(e.target.value)}
                    className="w-28 bg-gray-900 border border-gray-700 text-white px-2 py-2 rounded text-sm font-mono"
                  />
                </div>
                <button type="submit" className="px-3 py-2 bg-green-600 hover:bg-green-500 text-white rounded text-sm font-bold">Ekle</button>
                <button type="button" onClick={() => setShowBuy(false)} className="px-3 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded text-sm">İptal</button>
              </form>
            )}

            {/* Metrics table */}
            <div className="bg-gray-800/40 rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-bold text-gray-300">Temel Oranlar</h3>
                {!editing ? (
                  <button onClick={() => setEditing(true)} className="text-xs text-blue-400 hover:text-blue-300">✎ Elle düzelt</button>
                ) : (
                  <div className="flex gap-2">
                    <button onClick={() => { setEditing(false); setOverrideDraft(report.overrides || {}); }} className="text-xs text-gray-400 hover:text-white">İptal</button>
                    <button onClick={saveOverrides} disabled={saving} className="text-xs text-green-400 hover:text-green-300 font-bold">{saving ? 'Kaydediliyor…' : 'Kaydet'}</button>
                  </div>
                )}
              </div>

              {/* Sector / category (text override) */}
              <div className="flex items-center justify-between text-sm border-b border-gray-800/50 py-1 mb-1">
                <span className="text-gray-400">
                  Sektör / Kategori
                  {overrides.sector != null && <span className="ml-1 text-[10px] text-orange-400" title="Elle atandı">✎</span>}
                </span>
                {editing ? (
                  <input
                    type="text"
                    value={overrideDraft.sector ?? ''}
                    placeholder={m.sector || 'örn. Bankacılık'}
                    onChange={(e) => setOverrideDraft({ ...overrideDraft, sector: e.target.value })}
                    className="w-48 bg-gray-900 border border-gray-700 text-white px-2 py-0.5 rounded text-xs"
                  />
                ) : (
                  <span className={overrides.sector != null ? 'text-orange-300' : 'text-white'}>{m.sector || '—'}</span>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5">
                {METRIC_ROWS.map((row) => {
                  const overridden = overrides[row.key] != null;
                  return (
                    <div key={row.key} className="flex items-center justify-between text-sm border-b border-gray-800/50 py-1">
                      <span className="text-gray-400">
                        {row.label}
                        {overridden && <span className="ml-1 text-[10px] text-orange-400" title="Elle düzeltildi">✎</span>}
                      </span>
                      {editing ? (
                        <input
                          type="number"
                          step="any"
                          value={overrideDraft[row.key] ?? ''}
                          placeholder={m[row.key] != null ? String(m[row.key]) : '—'}
                          onChange={(e) => setOverrideDraft({ ...overrideDraft, [row.key]: e.target.value })}
                          className="w-24 bg-gray-900 border border-gray-700 text-white text-right px-2 py-0.5 rounded font-mono text-xs"
                        />
                      ) : (
                        <span className={`font-mono ${overridden ? 'text-orange-300' : 'text-white'}`}>
                          {m[row.key] == null ? '—' : `${fmt(m[row.key])}${row.unit}`}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
              {editing && (
                <p className="text-[11px] text-gray-500 mt-2">
                  Boş bırakılan alanlarda yfinance değeri kullanılır. Yüzde alanlarını yüzde olarak gir (ör. 4.07).
                </p>
              )}
            </div>

            {/* Financial statements */}
            <div className="bg-gray-800/40 rounded-lg p-3">
              <div className="flex gap-2 mb-3">
                {[['income', 'Gelir Tablosu'], ['balance', 'Bilanço'], ['cashflow', 'Nakit Akışı']].map(([k, lbl]) => (
                  <button
                    key={k}
                    onClick={() => setStmtTab(k)}
                    className={`px-3 py-1 rounded text-xs font-medium transition-colors ${stmtTab === k ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}`}
                  >
                    {lbl}
                  </button>
                ))}
              </div>
              <StatementTable data={report.financials?.[stmtTab]} />
            </div>

            {/* Recent dividends */}
            {report.dividends?.length > 0 && (
              <div className="bg-gray-800/40 rounded-lg p-3">
                <h3 className="text-sm font-bold text-gray-300 mb-2">Son Temettüler</h3>
                <div className="flex flex-wrap gap-2">
                  {report.dividends.slice(-8).reverse().map((d, i) => (
                    <span key={i} className="text-xs bg-gray-900 border border-gray-700 rounded px-2 py-1 font-mono text-gray-300">
                      {d.date}: {cur}{fmt(d.amount, 4)}
                    </span>
                  ))}
                </div>
              </div>
            )}
            </>)}
          </div>
        )}
      </div>
    </div>
  );
}
