import { useEffect, useRef, useState } from 'react';
import { createChart, CandlestickSeries, LineSeries } from 'lightweight-charts';
import { marketFlag } from '../../utils/market';

const API_BASE = import.meta.env.VITE_API_BASE || '';

const scoreColor = (s) =>
  s == null ? 'text-gray-500' : s >= 70 ? 'text-green-400' : s >= 50 ? 'text-blue-400' : s >= 30 ? 'text-yellow-400' : 'text-red-400';

const TREND_CLS = {
  'yükseliş': 'bg-green-500/15 text-green-300 border-green-500/40',
  'düşüş': 'bg-red-500/15 text-red-300 border-red-500/40',
  'yatay': 'bg-gray-600/30 text-gray-300 border-gray-600/50',
};

export default function TechnicalModal({ ticker, market, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const priceRef = useRef(null);
  const rsiRef = useRef(null);
  const chartsRef = useRef([]);

  // fetch
  useEffect(() => {
    let on = true;
    (async () => {
      setLoading(true);
      try {
        const mq = market ? `?market=${encodeURIComponent(market)}` : '';
        const res = await fetch(`${API_BASE}/investing/chart-data/${encodeURIComponent(ticker)}${mq}`);
        const d = await res.json();
        if (on) setData(d);
      } catch {
        if (on) setData({ valid: false });
      } finally {
        if (on) setLoading(false);
      }
    })();
    return () => { on = false; };
  }, [ticker, market]);

  // build charts when data is ready
  useEffect(() => {
    if (!data || !data.valid || !priceRef.current || !rsiRef.current) return;

    // cleanup any previous charts
    chartsRef.current.forEach((c) => { try { c.remove(); } catch { /* noop */ } });
    chartsRef.current = [];

    const common = {
      layout: { background: { type: 'solid', color: '#0d1117' }, textColor: '#9ca3af' },
      grid: { vertLines: { color: '#1f2937' }, horzLines: { color: '#1f2937' } },
      rightPriceScale: { borderColor: '#374151' },
      timeScale: { borderColor: '#374151', timeVisible: false },
      crosshair: { mode: 1 },
    };
    const toSec = (ms) => Math.floor(ms / 1000);

    // --- price chart ---
    const priceChart = createChart(priceRef.current, { width: priceRef.current.clientWidth, height: 320, ...common });
    const candle = priceChart.addSeries(CandlestickSeries, {
      upColor: '#22c55e', downColor: '#ef4444',
      borderUpColor: '#22c55e', borderDownColor: '#ef4444',
      wickUpColor: '#22c55e', wickDownColor: '#ef4444',
    });
    candle.setData(data.candles.map((c) => ({ time: toSec(c.time), open: c.open, high: c.high, low: c.low, close: c.close })));

    const addLine = (chart, points, color, width = 2) => {
      if (!points?.length) return;
      const s = chart.addSeries(LineSeries, { color, lineWidth: width, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
      s.setData(points.map((p) => ({ time: toSec(p.time), value: p.value })));
    };
    addLine(priceChart, data.indicators?.ema50, '#3b82f6');
    addLine(priceChart, data.indicators?.ema200, '#f59e0b');

    // --- RSI pane ---
    const rsiChart = createChart(rsiRef.current, { width: rsiRef.current.clientWidth, height: 130, ...common });
    const rsiSeries = rsiChart.addSeries(LineSeries, {
      color: '#a855f7', lineWidth: 2, priceLineVisible: false, lastValueVisible: true,
      autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }),
    });
    rsiSeries.setData((data.indicators?.rsi || []).map((p) => ({ time: toSec(p.time), value: p.value })));
    rsiSeries.createPriceLine({ price: 70, color: '#ef4444', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: '70' });
    rsiSeries.createPriceLine({ price: 30, color: '#22c55e', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: '30' });

    priceChart.timeScale().fitContent();
    rsiChart.timeScale().fitContent();

    // keep the two time axes in sync
    const sync = (src, dst) => src.timeScale().subscribeVisibleLogicalRangeChange((r) => {
      if (r) dst.timeScale().setVisibleLogicalRange(r);
    });
    sync(priceChart, rsiChart);
    sync(rsiChart, priceChart);

    const onResize = () => {
      priceChart.applyOptions({ width: priceRef.current?.clientWidth || 600 });
      rsiChart.applyOptions({ width: rsiRef.current?.clientWidth || 600 });
    };
    window.addEventListener('resize', onResize);
    chartsRef.current = [priceChart, rsiChart];

    return () => {
      window.removeEventListener('resize', onResize);
      chartsRef.current.forEach((c) => { try { c.remove(); } catch { /* noop */ } });
      chartsRef.current = [];
    };
  }, [data]);

  const tech = data?.technical;

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-[60] p-2 sm:p-4" onClick={onClose}>
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-4xl max-h-[92vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-800 sticky top-0 bg-gray-900 z-10">
          <div className="flex items-center gap-2">
            <span>{marketFlag(data?.market || market)}</span>
            <h2 className="text-lg font-bold text-white">📈 Teknik Analiz — {ticker.replace('.IS', '')}</h2>
          </div>
          <button onClick={onClose} className="text-red-400 hover:text-red-300 text-xl px-2">✕</button>
        </div>

        {loading ? (
          <div className="py-20 text-center text-gray-400">Yükleniyor… <span className="animate-spin inline-block">⏳</span></div>
        ) : !data?.valid ? (
          <div className="py-20 text-center text-gray-500">Bu sembol için grafik verisi bulunamadı.</div>
        ) : (
          <div className="p-4 space-y-4">
            {/* Score + readings */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="bg-gray-800/60 rounded-lg p-3 text-center">
                <div className="text-xs text-gray-400 mb-1">Teknik Skor</div>
                <div className={`text-3xl font-extrabold ${scoreColor(tech?.score)}`}>{tech?.score == null ? '—' : tech.score}</div>
                <div className="h-1.5 bg-gray-700 rounded-full mt-2 overflow-hidden">
                  <div className={`h-full ${tech?.score >= 70 ? 'bg-green-500' : tech?.score >= 50 ? 'bg-blue-500' : tech?.score >= 30 ? 'bg-yellow-500' : 'bg-red-500'}`} style={{ width: `${tech?.score || 0}%` }} />
                </div>
              </div>
              <div className="sm:col-span-2 bg-gray-800/60 rounded-lg p-3 space-y-1.5">
                <div className="flex flex-wrap gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded border font-bold ${TREND_CLS[tech?.trend] || ''}`}>Trend: {tech?.trend}</span>
                  <span className="text-xs px-2 py-0.5 rounded border border-gray-600/50 bg-gray-700/40 text-gray-300">Momentum: {tech?.momentum}</span>
                </div>
                <ul className="text-xs text-gray-300 space-y-0.5 mt-1">
                  {tech?.readings?.map((r, i) => <li key={i}>• {r}</li>)}
                </ul>
              </div>
            </div>

            {/* Verdict */}
            {tech?.verdict && (
              <div className="text-sm text-gray-200 bg-blue-500/10 border border-blue-500/30 rounded-lg p-3">
                💬 {tech.verdict}
              </div>
            )}

            {/* Price chart */}
            <div>
              <div className="flex items-center gap-3 text-xs text-gray-400 mb-1">
                <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-[#3b82f6]" /> EMA50</span>
                <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-[#f59e0b]" /> EMA200 (200 günlük ort.)</span>
              </div>
              <div ref={priceRef} className="w-full" />
            </div>

            {/* RSI pane */}
            <div>
              <div className="text-xs text-gray-400 mb-1">RSI (14) — 70 üstü aşırı alım (pahalı), 30 altı aşırı satım (ucuz)</div>
              <div ref={rsiRef} className="w-full" />
            </div>

            <p className="text-[11px] text-gray-600">
              Günlük mum, ~2 yıl. Teknik analiz giriş zamanını iyileştirir; uzun vadede tek başına belirleyici değildir.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
