// Landing page: choose between the two sub-apps.
export default function LandingPage({ onSelect }) {
  return (
    <div className="min-h-screen bg-terminal-dark flex flex-col items-center justify-center px-4">
      <div className="text-center mb-10">
        <h1 className="text-4xl sm:text-5xl font-extrabold text-white tracking-tight">
          Financia
        </h1>
        <p className="text-gray-500 mt-3 text-sm sm:text-base">
          BIST &amp; ABD — tek panelde gün içi trade ve uzun vadeli yatırım
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 w-full max-w-3xl">
        {/* Intraday trading */}
        <button
          onClick={() => onSelect('trading')}
          className="group text-left rounded-2xl border border-gray-800 bg-gray-900/60 hover:border-green-500/60 hover:bg-gray-900 p-7 transition-all"
        >
          <div className="text-4xl mb-4">🎯</div>
          <h2 className="text-xl font-bold text-white group-hover:text-green-400 transition-colors">
            Gün İçi Trade
          </h2>
          <p className="text-gray-500 text-sm mt-2 leading-relaxed">
            Stratejiler, canlı sinyaller, gün sonu analizi ve simülasyon/backtest.
            Küçük, sık kâr için R-bazlı işlemler.
          </p>
          <span className="inline-block mt-5 text-green-400 text-sm font-semibold">
            Aç →
          </span>
        </button>

        {/* Long-term investing */}
        <button
          onClick={() => onSelect('investing')}
          className="group text-left rounded-2xl border border-gray-800 bg-gray-900/60 hover:border-blue-500/60 hover:bg-gray-900 p-7 transition-all"
        >
          <div className="text-4xl mb-4">📈</div>
          <h2 className="text-xl font-bold text-white group-hover:text-blue-400 transition-colors">
            Uzun Vadeli Yatırım
          </h2>
          <p className="text-gray-500 text-sm mt-2 leading-relaxed">
            Portföy takibi, temel analiz tarayıcı (temettü &amp; büyüme skoru),
            ayrıntılı hisse raporları ve temettü geliri tahmini.
          </p>
          <span className="inline-block mt-5 text-blue-400 text-sm font-semibold">
            Aç →
          </span>
        </button>
      </div>

      <p className="text-gray-700 text-xs mt-10">
        Midas ile manuel işlem · yfinance verisi
      </p>
    </div>
  );
}
