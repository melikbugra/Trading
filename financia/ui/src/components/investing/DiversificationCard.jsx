import { useState } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || '';

const LEVEL_CLS = {
  high: 'bg-red-500/10 border-red-500/40 text-red-300',
  medium: 'bg-yellow-500/10 border-yellow-500/40 text-yellow-300',
  info: 'bg-blue-500/10 border-blue-500/40 text-blue-300',
  ok: 'bg-green-500/10 border-green-500/40 text-green-300',
};
const LEVEL_ICON = { high: '🔴', medium: '🟡', info: 'ℹ️', ok: '🟢' };

const BAR_COLORS = ['bg-blue-500', 'bg-purple-500', 'bg-green-500', 'bg-yellow-500', 'bg-pink-500', 'bg-cyan-500', 'bg-orange-500', 'bg-gray-500'];

export default function DiversificationCard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  const load = async () => {
    setLoading(true);
    setOpen(true);
    try {
      const res = await fetch(`${API_BASE}/investing/diversification`);
      setData(await res.json());
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mb-4 bg-gray-900 border border-gray-800 rounded-lg">
      <div className="flex items-center justify-between p-3">
        <h3 className="text-sm font-bold text-gray-300">📊 Risk &amp; Dağılım Analizi</h3>
        <button onClick={load} disabled={loading} className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-white rounded text-xs font-bold">
          {loading ? 'Analiz ediliyor…' : (data ? '↻ Yenile' : 'Analiz Et')}
        </button>
      </div>

      {open && !loading && data && data.holdings > 0 && (
        <div className="px-3 pb-3 space-y-4">
          {/* Warnings */}
          <div className="space-y-1.5">
            {data.warnings.map((w, i) => (
              <div key={i} className={`text-xs rounded border px-2 py-1.5 ${LEVEL_CLS[w.level] || LEVEL_CLS.info}`}>
                {LEVEL_ICON[w.level] || ''} {w.message}
              </div>
            ))}
          </div>

          {/* Sector distribution */}
          <div>
            <div className="text-xs text-gray-500 mb-1">Sektör Dağılımı</div>
            <div className="flex h-3 rounded-full overflow-hidden mb-1">
              {data.sectors.map((s, i) => (
                <div key={s.sector} className={BAR_COLORS[i % BAR_COLORS.length]} style={{ width: `${s.weight}%` }} title={`${s.sector}: %${s.weight}`} />
              ))}
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-0.5">
              {data.sectors.map((s, i) => (
                <span key={s.sector} className="text-[11px] text-gray-400 flex items-center gap-1">
                  <span className={`inline-block w-2 h-2 rounded-full ${BAR_COLORS[i % BAR_COLORS.length]}`} />
                  {s.sector} %{s.weight}
                </span>
              ))}
            </div>
          </div>

          {/* Currency split + top positions */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <div className="text-xs text-gray-500 mb-1">Para Birimi</div>
              {data.currencies.map((c) => (
                <div key={c.currency} className="flex justify-between text-xs text-gray-300 border-b border-gray-800/50 py-0.5">
                  <span>{c.currency}</span><span className="font-mono">%{c.weight}</span>
                </div>
              ))}
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">En Büyük Pozisyonlar</div>
              {data.positions.slice(0, 5).map((p) => (
                <div key={p.symbol} className="flex justify-between text-xs text-gray-300 border-b border-gray-800/50 py-0.5">
                  <span>{p.market === 'us' ? '🇺🇸' : '🇹🇷'} {p.symbol}</span><span className="font-mono">%{p.weight}</span>
                </div>
              ))}
            </div>
          </div>

          <p className="text-[11px] text-gray-600">
            ₺ ve $ pozisyonlar USD/TRY{data.usdtry ? ` (${data.usdtry.toFixed(2)})` : ''} ile ortak tabana (₺) çevrilerek hesaplandı. Eşikler: sektör %40, tek pozisyon %25.
          </p>
        </div>
      )}

      {open && !loading && data && data.holdings === 0 && (
        <div className="px-3 pb-3 text-xs text-gray-500">Portföyünde pozisyon yok.</div>
      )}
    </div>
  );
}
