import { useEffect, useState } from 'react';
import { useToast } from '../../contexts/ToastContext';
import { dateTag } from '../../utils/dates';

const API_BASE = import.meta.env.VITE_API_BASE || '';

function DateCell({ value }) {
  const tag = dateTag(value);
  return (
    <span className="whitespace-nowrap">
      {value ? new Date(value).toLocaleDateString('tr-TR', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
      {tag && <span className={`ml-1.5 text-[10px] px-1.5 py-0.5 rounded border ${tag.cls}`}>{tag.text}</span>}
    </span>
  );
}

const SCOPES = [
  { key: 'all', label: 'Tümü' },
  { key: 'portfolio', label: 'Portföy' },
  { key: 'watchlist', label: 'İzleme' },
];

const fmtDate = (s) => {
  if (!s) return '—';
  try {
    const d = new Date(s);
    if (Number.isNaN(d.getTime())) return s;
    return d.toLocaleDateString('tr-TR', { day: '2-digit', month: 'short', year: 'numeric' });
  } catch { return s; }
};

const fmtDateTime = (s) => {
  if (!s) return '';
  try {
    const d = new Date(s);
    if (Number.isNaN(d.getTime())) return s;
    return d.toLocaleString('tr-TR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
  } catch { return s; }
};

const flag = (m) => (m === 'us' ? '🇺🇸' : '🇹🇷');

export default function NewsPanel() {
  const { addToast } = useToast();
  const [scope, setScope] = useState('all');
  const [data, setData] = useState({ tickers: 0, news: [], events: [] });
  const [loading, setLoading] = useState(true);

  const load = async (sc = scope) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/investing/news?scope=${sc}`);
      setData(await res.json());
    } catch {
      addToast('Haberler yüklenemedi', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(scope); /* eslint-disable-next-line */ }, [scope]);

  return (
    <div>
      {/* Controls */}
      <div className="flex items-center gap-2 mb-4">
        <div className="flex gap-1">
          {SCOPES.map((s) => (
            <button
              key={s.key}
              onClick={() => setScope(s.key)}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${scope === s.key ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}`}
            >
              {s.label}
            </button>
          ))}
        </div>
        <button onClick={() => load()} className="ml-auto px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white rounded text-sm">↻ Yenile</button>
      </div>

      {loading ? (
        <div className="text-gray-400 text-center py-16">Yükleniyor… <span className="animate-spin inline-block">⏳</span></div>
      ) : data.tickers === 0 ? (
        <div className="text-gray-500 text-center py-16 border border-dashed border-gray-800 rounded-lg">
          Portföyünde/izleme listende hisse yok. Önce hisse ekle.
        </div>
      ) : (
        <div className="space-y-6">
          {/* Upcoming events */}
          <div>
            <h3 className="text-sm font-bold text-gray-300 mb-2">📅 Yaklaşan Tarihler (Bilanço / Temettü)</h3>
            {data.events.length === 0 ? (
              <p className="text-gray-500 text-sm">Yaklaşan tarih bulunamadı.</p>
            ) : (
              <div className="overflow-x-auto border border-gray-800 rounded-lg">
                <table className="w-full text-sm">
                  <thead className="bg-gray-900 text-gray-500">
                    <tr>
                      <th className="text-left px-3 py-2">Hisse</th>
                      <th className="text-left px-3 py-2">Bilanço Tarihi</th>
                      <th className="text-left px-3 py-2">Ex-Temettü</th>
                      <th className="text-left px-3 py-2 hidden sm:table-cell">Temettü Ödeme</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.events.map((e) => (
                      <tr key={e.ticker} className="border-t border-gray-800">
                        <td className="px-3 py-2 font-mono font-bold text-white">{flag(e.market)} {e.symbol}</td>
                        <td className="px-3 py-2 text-gray-300"><DateCell value={e.earnings_date} /></td>
                        <td className="px-3 py-2 text-gray-300"><DateCell value={e.ex_dividend_date} /></td>
                        <td className="px-3 py-2 text-gray-300 hidden sm:table-cell"><DateCell value={e.dividend_date} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* News */}
          <div>
            <h3 className="text-sm font-bold text-gray-300 mb-2">📰 Haberler ({data.news.length})</h3>
            {data.news.length === 0 ? (
              <p className="text-gray-500 text-sm">Haber bulunamadı.</p>
            ) : (
              <div className="space-y-2">
                {data.news.map((n, i) => (
                  <a
                    key={`${n.ticker}-${i}`}
                    href={n.link || '#'}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-lg p-3 transition-colors"
                  >
                    <div className="flex items-start gap-2">
                      <span className="text-xs font-mono font-bold text-blue-400 whitespace-nowrap mt-0.5">{flag(n.market)} {n.symbol}</span>
                      <div className="min-w-0">
                        <div className="text-white text-sm leading-snug">{n.title}</div>
                        <div className="text-gray-500 text-xs mt-1">
                          {n.publisher || 'Kaynak ?'}{n.published ? ` · ${fmtDateTime(n.published)}` : ''}
                          {n.type && n.type !== 'STORY' ? ` · ${n.type}` : ''}
                        </div>
                      </div>
                    </div>
                  </a>
                ))}
              </div>
            )}
            <p className="text-[11px] text-gray-600 mt-3">
              Kaynak: BIST → Google Haberler (Türkçe; Investing, Bloomberght, Mynet, Bigpara…) · ABD → Yahoo Finance.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
