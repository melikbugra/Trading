// Market id -> display helpers (mirrors financia/markets.py).
// Markets seen on the frontend: "bist100"/"bist", "us", "binance".

export function currencySymbol(market) {
    const m = (market || '').toLowerCase();
    if (m === 'us' || m === 'sp100' || m === 'nasdaq' || m === 'nyse') return '$';
    if (m === 'binance') return '$';
    return '₺'; // bist100 / bist / default
}

export function marketFlag(market) {
    const m = (market || '').toLowerCase();
    if (m === 'us' || m === 'sp100' || m === 'nasdaq' || m === 'nyse') return '🇺🇸';
    if (m === 'binance') return '₿';
    return '🇹🇷';
}
