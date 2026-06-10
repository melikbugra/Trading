import { useEffect, useRef, useState } from 'react';
import { useToast } from '../../contexts/ToastContext';
import { useWebSocket } from '../../contexts/WebSocketContext';

const API_BASE = import.meta.env.VITE_API_BASE || '';

// Triggers a bulk fundamental scan for a specific set of tickers (portfolio or
// watchlist) and reloads the page (onDone) when it finishes. Reuses the global
// `investing_scan` websocket progress.
export default function AnalyzeButton({ getBody, label, onDone, className }) {
  const { addToast } = useToast();
  const { investingScanProgress } = useWebSocket();
  const [scanning, setScanning] = useState(false);
  const startedRef = useRef(false); // did THIS button start the running scan
  const lastDoneRef = useRef(null);

  useEffect(() => {
    const p = investingScanProgress;
    if (!p || !startedRef.current) return;
    if (p.status === 'completed') {
      const key = `${p.label}-${p.total}-${p.count}`;
      if (lastDoneRef.current !== key) {
        lastDoneRef.current = key;
        setScanning(false);
        startedRef.current = false;
        const skipped = p.skipped?.length || 0;
        addToast(
          `Analiz tamam: ${p.count} hisse skorlandı` + (skipped ? `, ${skipped} atlandı` : ''),
          'success', 5000,
        );
        onDone?.();
      }
    }
    // eslint-disable-next-line
  }, [investingScanProgress]);

  const run = async () => {
    const body = getBody();
    if (!body) {
      addToast('Analiz edilecek hisse yok', 'error');
      return;
    }
    setScanning(true);
    startedRef.current = true;
    try {
      const res = await fetch(`${API_BASE}/investing/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const d = await res.json();
        addToast(`${d.total} hisse analiz ediliyor…`, 'info', 3000);
      } else if (res.status === 409) {
        addToast('Zaten bir tarama çalışıyor', 'error');
        setScanning(false);
        startedRef.current = false;
      } else {
        addToast('Analiz başlatılamadı', 'error');
        setScanning(false);
        startedRef.current = false;
      }
    } catch {
      addToast('Analiz başlatılamadı', 'error');
      setScanning(false);
      startedRef.current = false;
    }
  };

  const p = investingScanProgress;
  const showProg = scanning && startedRef.current && p && p.status !== 'completed';

  return (
    <span className="inline-flex items-center gap-2">
      <button
        onClick={run}
        disabled={scanning}
        className={className || 'px-3 py-2 bg-green-600 hover:bg-green-500 disabled:bg-gray-700 text-white rounded text-sm font-bold transition-colors'}
      >
        {scanning ? 'Analiz ediliyor…' : label}
      </button>
      {showProg && <span className="text-xs text-gray-400 font-mono">{p.current}/{p.total}</span>}
    </span>
  );
}
