// Shared market (borsa) + sector filter bar for stock lists.
const MARKETS = [
  { key: 'all', label: 'Tümü' },
  { key: 'bist', label: '🇹🇷 BIST' },
  { key: 'us', label: '🇺🇸 ABD' },
];

export default function ListFilters({ market, setMarket, sector, setSector, sectors }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex gap-1">
        {MARKETS.map((m) => (
          <button
            key={m.key}
            onClick={() => setMarket(m.key)}
            className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${market === m.key ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}`}
          >
            {m.label}
          </button>
        ))}
      </div>
      {sectors && sectors.length > 0 && (
        <select
          value={sector}
          onChange={(e) => setSector(e.target.value)}
          className="bg-gray-800 border border-gray-700 text-gray-300 px-2 py-1 rounded text-xs"
        >
          <option value="all">Tüm sektörler</option>
          {sectors.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      )}
    </div>
  );
}

// Helper: unique sorted sector list from rows (using a getter).
export function uniqueSectors(rows, getSector) {
  return [...new Set(rows.map(getSector).filter(Boolean))].sort();
}

// Prefer yfinance's specific industry (e.g. Semiconductors) over its broad
// sector (e.g. Technology), while keeping the broad sector as a fallback.
export function specificSector(row) {
  return row?.industry || row?.sector || '';
}

// Type-as-you-go search box with a clear (✕) button.
export function SearchBox({ value, onChange, placeholder = '🔎 Ara (sembol / sektör)' }) {
  return (
    <div className="relative">
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="bg-gray-800 border border-gray-700 text-white px-2 py-1 rounded text-xs w-44"
      />
      {value && (
        <button
          onClick={() => onChange('')}
          className="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white text-xs"
        >
          ✕
        </button>
      )}
    </div>
  );
}
