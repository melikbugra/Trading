import { useEffect, useRef, useState } from 'react';
import { createChart, CandlestickSeries, LineSeries, HistogramSeries, AreaSeries } from 'lightweight-charts';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function ChartModal({ ticker, market, strategyId, onClose }) {
    const chartContainerRef = useRef(null);
    const indicatorContainerRef = useRef(null);
    const chartAreaRef = useRef(null);
    const chartRef = useRef(null);
    const indicatorChartRef = useRef(null);
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [isFullscreen, setIsFullscreen] = useState(true); // Default to fullscreen
    const [chartRatio, setChartRatio] = useState(0.5); // Price chart gets 75% (3:1 ratio)
    const [availableHeight, setAvailableHeight] = useState(600);

    const displayTicker = ticker?.replace('.IS', '').replace('TRY', '') || '';

    // Calculate heights based on ratio
    const labelHeight = 24; // Height for labels
    const resizerHeight = 10; // Height for resizer
    const totalChartSpace = availableHeight - (labelHeight * 2) - resizerHeight;
    const chartHeight = Math.floor(totalChartSpace * chartRatio);
    const macdHeight = totalChartSpace - chartHeight;

    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                const url = `${API_BASE}/strategies/chart-data/${ticker}?market=${market}${strategyId ? `&strategy_id=${strategyId}` : ''}`;
                const res = await fetch(url);
                if (!res.ok) throw new Error('Veri alınamadı');
                const json = await res.json();
                setData(json);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        if (ticker) {
            fetchData();
        }
    }, [ticker, market, strategyId]);

    useEffect(() => {
        if (!data || !chartContainerRef.current) return;

        // Clean up previous charts
        if (chartRef.current) {
            chartRef.current.remove();
            chartRef.current = null;
        }
        if (indicatorChartRef.current) {
            indicatorChartRef.current.remove();
            indicatorChartRef.current = null;
        }

        // Create main chart
        const chart = createChart(chartContainerRef.current, {
            width: chartContainerRef.current.clientWidth,
            height: chartHeight,
            layout: {
                background: { type: 'solid', color: '#1a1a2e' },
                textColor: '#d1d5db',
            },
            grid: {
                vertLines: { color: '#2d2d44' },
                horzLines: { color: '#2d2d44' },
            },
            crosshair: {
                mode: 1,
            },
            rightPriceScale: {
                borderColor: '#4b5563',
            },
            timeScale: {
                borderColor: '#4b5563',
                timeVisible: true,
                secondsVisible: false,
            },
        });
        chartRef.current = chart;

        // Candlestick series (v4 API)
        const candlestickSeries = chart.addSeries(CandlestickSeries, {
            upColor: '#22c55e',
            downColor: '#ef4444',
            borderDownColor: '#ef4444',
            borderUpColor: '#22c55e',
            wickDownColor: '#ef4444',
            wickUpColor: '#22c55e',
            lastValueVisible: false,  // Hide automatic last price label
            priceLineVisible: false,  // Hide automatic price line
        });

        // Convert candle data (add Turkey timezone offset: UTC+3 = 10800 seconds)
        const turkeyOffset = 3 * 60 * 60;
        const candleData = data.candles.map(c => ({
            time: (c.time / 1000) + turkeyOffset, // Convert ms to seconds + Turkey offset
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
        }));
        candlestickSeries.setData(candleData);

        // Calculate price range including signal levels
        let minPrice = Math.min(...candleData.map(c => c.low));
        let maxPrice = Math.max(...candleData.map(c => c.high));

        if (data.signal) {
            const { entry_price, stop_loss, take_profit } = data.signal;
            if (entry_price) {
                minPrice = Math.min(minPrice, entry_price);
                maxPrice = Math.max(maxPrice, entry_price);
            }
            if (stop_loss) {
                minPrice = Math.min(minPrice, stop_loss);
                maxPrice = Math.max(maxPrice, stop_loss);
            }
            if (take_profit) {
                minPrice = Math.min(minPrice, take_profit);
                maxPrice = Math.max(maxPrice, take_profit);
            }
        }
        if (data.current_price) {
            minPrice = Math.min(minPrice, data.current_price);
            maxPrice = Math.max(maxPrice, data.current_price);
        }

        // Add padding (5% on each side)
        const range = maxPrice - minPrice;
        const padding = range * 0.05;
        minPrice -= padding;
        maxPrice += padding;

        // Set autoscale provider to include signal levels
        candlestickSeries.applyOptions({
            autoscaleInfoProvider: () => ({
                priceRange: {
                    minValue: minPrice,
                    maxValue: maxPrice,
                },
            }),
        });

        // EMA200 line
        if (data.indicators?.ema200?.length > 0) {
            const emaSeries = chart.addSeries(LineSeries, {
                color: '#f59e0b',
                lineWidth: 2,
            });
            const emaData = data.indicators.ema200.map(e => ({
                time: (e.time / 1000) + turkeyOffset,
                value: e.value,
            }));
            emaSeries.setData(emaData);
        }

        // Add price lines and projection zones for signal levels
        if (data.signal) {
            const { entry_price, stop_loss, take_profit, triggered_at } = data.signal;

            // Find the signal start time (triggered_at or last 20% of candles)
            let signalStartTime;
            if (triggered_at) {
                signalStartTime = (new Date(triggered_at).getTime() / 1000) + turkeyOffset;
            } else {
                // Default to ~20% from the end of the chart
                const startIndex = Math.floor(candleData.length * 0.8);
                signalStartTime = candleData[startIndex]?.time || candleData[candleData.length - 1].time;
            }
            const signalEndTime = candleData[candleData.length - 1].time + 86400 * 10; // Extend 10 days into future

            // Create projection zones (profit zone - green, loss zone - red)
            if (entry_price && take_profit) {
                // Profit zone (entry to take_profit) - green
                const profitZoneSeries = chart.addSeries(AreaSeries, {
                    lineColor: 'rgba(34, 197, 94, 0.5)',
                    topColor: 'rgba(34, 197, 94, 0.3)',
                    bottomColor: 'rgba(34, 197, 94, 0.05)',
                    lineWidth: 1,
                    priceLineVisible: false,
                    lastValueVisible: false,
                    crosshairMarkerVisible: false,
                });
                profitZoneSeries.setData([
                    { time: signalStartTime, value: take_profit },
                    { time: signalEndTime, value: take_profit },
                ]);

                // Entry line area (as baseline for profit zone)
                const profitBaselineSeries = chart.addSeries(LineSeries, {
                    color: 'rgba(34, 197, 94, 0.3)',
                    lineWidth: 0,
                    priceLineVisible: false,
                    lastValueVisible: false,
                    crosshairMarkerVisible: false,
                });
                profitBaselineSeries.setData([
                    { time: signalStartTime, value: entry_price },
                    { time: signalEndTime, value: entry_price },
                ]);
            }

            if (entry_price && stop_loss) {
                // Loss zone (entry to stop_loss) - red
                const lossZoneSeries = chart.addSeries(AreaSeries, {
                    lineColor: 'rgba(239, 68, 68, 0.5)',
                    topColor: 'rgba(239, 68, 68, 0.05)',
                    bottomColor: 'rgba(239, 68, 68, 0.3)',
                    lineWidth: 1,
                    priceLineVisible: false,
                    lastValueVisible: false,
                    crosshairMarkerVisible: false,
                    invertFilledArea: true,
                });
                lossZoneSeries.setData([
                    { time: signalStartTime, value: stop_loss },
                    { time: signalEndTime, value: stop_loss },
                ]);
            }

            // Add price lines (on top of zones)
            if (entry_price) {
                candlestickSeries.createPriceLine({
                    price: entry_price,
                    color: '#3b82f6',
                    lineWidth: 2,
                    lineStyle: 0,
                    axisLabelVisible: true,
                    title: 'Giriş',
                });
            }
            if (stop_loss) {
                candlestickSeries.createPriceLine({
                    price: stop_loss,
                    color: '#ef4444',
                    lineWidth: 2,
                    lineStyle: 2,
                    axisLabelVisible: true,
                    title: 'Zarar Kes',
                });
            }
            if (take_profit) {
                candlestickSeries.createPriceLine({
                    price: take_profit,
                    color: '#22c55e',
                    lineWidth: 2,
                    lineStyle: 2,
                    axisLabelVisible: true,
                    title: 'Kâr Al',
                });
            }
        }

        // Current price line
        if (data.current_price) {
            candlestickSeries.createPriceLine({
                price: data.current_price,
                color: '#8b5cf6',
                lineWidth: 1,
                lineStyle: 1,
                axisLabelVisible: true,
                title: 'Güncel',
            });
        }

        chart.timeScale().fitContent();

        // Create indicator chart (MACD or Stochastic RSI based on strategy type)
        const hasMACD = data.indicators?.macd?.length > 0;
        const hasStochRSI = data.indicators?.stoch_rsi?.length > 0;

        if (indicatorContainerRef.current && (hasMACD || hasStochRSI)) {
            const indicatorChart = createChart(indicatorContainerRef.current, {
                width: indicatorContainerRef.current.clientWidth,
                height: macdHeight,
                layout: {
                    background: { type: 'solid', color: '#1a1a2e' },
                    textColor: '#d1d5db',
                },
                grid: {
                    vertLines: { color: '#2d2d44' },
                    horzLines: { color: '#2d2d44' },
                },
                rightPriceScale: {
                    borderColor: '#4b5563',
                },
                timeScale: {
                    borderColor: '#4b5563',
                    timeVisible: true,
                    secondsVisible: false,
                },
            });
            indicatorChartRef.current = indicatorChart;

            if (hasStochRSI) {
                // Stochastic RSI indicator
                const stochKLine = indicatorChart.addSeries(LineSeries, {
                    color: '#3b82f6',
                    lineWidth: 2,
                    title: '%K',
                });

                const stochDLine = indicatorChart.addSeries(LineSeries, {
                    color: '#f59e0b',
                    lineWidth: 2,
                    title: '%D',
                });

                const stochKData = data.indicators.stoch_rsi.map(s => ({
                    time: (s.time / 1000) + turkeyOffset,
                    value: s.k,
                }));
                const stochDData = data.indicators.stoch_rsi.map(s => ({
                    time: (s.time / 1000) + turkeyOffset,
                    value: s.d,
                }));

                stochKLine.setData(stochKData);
                stochDLine.setData(stochDData);

                // Add oversold (20) and overbought (80) reference lines
                stochKLine.createPriceLine({
                    price: 20,
                    color: '#22c55e',
                    lineWidth: 1,
                    lineStyle: 2,
                    axisLabelVisible: true,
                    title: '',
                });
                stochKLine.createPriceLine({
                    price: 80,
                    color: '#ef4444',
                    lineWidth: 1,
                    lineStyle: 2,
                    axisLabelVisible: true,
                    title: '',
                });

            } else if (hasMACD) {
                // MACD indicator
                const macdLine = indicatorChart.addSeries(LineSeries, {
                    color: '#3b82f6',
                    lineWidth: 2,
                });

                const signalLine = indicatorChart.addSeries(LineSeries, {
                    color: '#f59e0b',
                    lineWidth: 2,
                });

                const histogram = indicatorChart.addSeries(HistogramSeries, {
                    color: '#22c55e',
                });

                const macdData = data.indicators.macd.map(m => ({
                    time: (m.time / 1000) + turkeyOffset,
                    value: m.macd,
                }));
                const signalData = data.indicators.macd.map(m => ({
                    time: (m.time / 1000) + turkeyOffset,
                    value: m.signal,
                }));
                const histData = data.indicators.macd.map(m => ({
                    time: (m.time / 1000) + turkeyOffset,
                    value: m.histogram,
                    color: m.histogram >= 0 ? '#22c55e' : '#ef4444',
                }));

                macdLine.setData(macdData);
                signalLine.setData(signalData);
                histogram.setData(histData);
            }

            indicatorChart.timeScale().fitContent();

            // Sync time scales
            chart.timeScale().subscribeVisibleLogicalRangeChange(range => {
                if (range) {
                    indicatorChart.timeScale().setVisibleLogicalRange(range);
                }
            });
            indicatorChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
                if (range) {
                    chart.timeScale().setVisibleLogicalRange(range);
                }
            });
        }

        // Resize handler
        const handleResize = () => {
            if (chartContainerRef.current && chartRef.current) {
                chartRef.current.applyOptions({
                    width: chartContainerRef.current.clientWidth,
                    height: chartHeight
                });
            }
            if (indicatorContainerRef.current && indicatorChartRef.current) {
                indicatorChartRef.current.applyOptions({
                    width: indicatorContainerRef.current.clientWidth,
                    height: macdHeight
                });
            }
        };

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            if (chartRef.current) {
                chartRef.current.remove();
                chartRef.current = null;
            }
            if (indicatorChartRef.current) {
                indicatorChartRef.current.remove();
                indicatorChartRef.current = null;
            }
        };
    }, [data, chartHeight, macdHeight]);

    // Calculate available height for charts
    useEffect(() => {
        const calculateHeight = () => {
            if (chartAreaRef.current) {
                const padding = 32; // p-4 = 16px * 2
                const height = chartAreaRef.current.clientHeight - padding;
                setAvailableHeight(Math.max(300, height));
            }
        };

        calculateHeight();
        window.addEventListener('resize', calculateHeight);
        return () => window.removeEventListener('resize', calculateHeight);
    }, []);

    // Trigger resize when fullscreen mode changes
    useEffect(() => {
        // Small delay to allow DOM to update
        const timer = setTimeout(() => {
            if (chartAreaRef.current) {
                const padding = 32;
                const height = chartAreaRef.current.clientHeight - padding;
                setAvailableHeight(Math.max(300, height));
            }
            if (chartContainerRef.current && chartRef.current) {
                chartRef.current.applyOptions({
                    width: chartContainerRef.current.clientWidth
                });
                chartRef.current.timeScale().fitContent();
            }
            if (indicatorContainerRef.current && indicatorChartRef.current) {
                indicatorChartRef.current.applyOptions({
                    width: indicatorContainerRef.current.clientWidth
                });
                indicatorChartRef.current.timeScale().fitContent();
            }
        }, 100);
        return () => clearTimeout(timer);
    }, [isFullscreen]);

    return (
        <div className="fixed inset-0 bg-black/90 flex items-center justify-center z-50 p-1 sm:p-2">
            <div className={`bg-gray-900 border border-gray-700 rounded-lg overflow-hidden flex flex-col transition-all duration-300 ${isFullscreen
                ? 'w-full h-full'
                : 'w-full max-w-5xl h-[85vh]'
                }`}>
                {/* Header */}
                <div className="flex items-center justify-between p-2 sm:p-3 border-b border-gray-700 bg-gray-800/50">
                    <div className="flex items-center gap-2 sm:gap-4">
                        <span className={`text-base sm:text-lg ${market === 'bist100' ? 'text-red-400' : 'text-yellow-400'}`}>
                            {market === 'bist100' ? '🇹🇷' : '₿'}
                        </span>
                        <h2 className="text-lg sm:text-xl font-bold text-white">{displayTicker}</h2>
                        {data?.current_price && (
                            <span className="text-lg sm:text-2xl font-mono text-purple-400">
                                ₺{data.current_price.toFixed(2)}
                            </span>
                        )}
                    </div>
                    <div className="flex items-center gap-1 sm:gap-2">
                        {/* Fullscreen Toggle */}
                        <button
                            onClick={() => setIsFullscreen(!isFullscreen)}
                            className="px-2 sm:px-3 py-1.5 sm:py-2 bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white rounded-lg text-sm transition-colors hidden sm:block"
                            title={isFullscreen ? 'Küçült' : 'Tam Ekran'}
                        >
                            {isFullscreen ? '⊙' : '⛶'}
                        </button>
                        <button
                            onClick={onClose}
                            className="px-2 sm:px-3 py-1.5 sm:py-2 bg-red-600/20 hover:bg-red-600/40 text-red-400 rounded-lg text-lg sm:text-xl transition-colors"
                        >
                            ✕
                        </button>
                    </div>
                </div>

                {/* Signal Info */}
                {data?.signal && (
                    <div className={`p-2 sm:p-4 border-b border-gray-700 ${data.signal.direction === 'long' ? 'bg-green-900/30' : 'bg-red-900/30'
                        }`}>
                        <div className="flex flex-wrap items-center gap-2 sm:gap-6">
                            <div className="flex items-center gap-2">
                                <span className={`text-sm sm:text-lg font-bold ${data.signal.direction === 'long' ? 'text-green-400' : 'text-red-400'
                                    }`}>
                                    {data.signal.direction === 'long' ? '📈 LONG' : '📉 SHORT'}
                                </span>
                                <span className={`px-1.5 sm:px-2 py-0.5 sm:py-1 rounded text-xs font-bold ${data.signal.status === 'triggered' ? 'bg-blue-600 text-white' :
                                    data.signal.status === 'pending' ? 'bg-yellow-600 text-white' :
                                        data.signal.status === 'entered' ? 'bg-green-600 text-white' :
                                            'bg-gray-600 text-white'
                                    }`}>
                                    {data.signal.status === 'triggered' ? 'Tetik' :
                                        data.signal.status === 'pending' ? 'Bekle' :
                                            data.signal.status === 'entered' ? 'Poz' :
                                                data.signal.status}
                                </span>
                            </div>

                            {data.signal.entry_price && (
                                <div className="text-xs sm:text-sm">
                                    <span className="text-gray-400">G: </span>
                                    <span className="text-blue-400 font-mono font-bold">₺{data.signal.entry_price.toFixed(2)}</span>
                                </div>
                            )}
                            {data.signal.stop_loss && (
                                <div className="text-xs sm:text-sm">
                                    <span className="text-gray-400">SL: </span>
                                    <span className="text-red-400 font-mono font-bold">₺{data.signal.stop_loss.toFixed(2)}</span>
                                </div>
                            )}
                            {data.signal.take_profit && (
                                <div className="text-xs sm:text-sm">
                                    <span className="text-gray-400">TP: </span>
                                    <span className="text-green-400 font-mono font-bold">₺{data.signal.take_profit.toFixed(2)}</span>
                                </div>
                            )}
                        </div>
                        {data.signal.notes && (
                            <p className="text-gray-400 text-xs sm:text-sm mt-1 sm:mt-2 italic hidden sm:block">{data.signal.notes}</p>
                        )}
                    </div>
                )}

                {/* Chart Area */}
                <div ref={chartAreaRef} className="flex-1 overflow-hidden p-4 min-h-0">
                    {loading && (
                        <div className="flex items-center justify-center h-full">
                            <div className="text-gray-400">
                                <span className="animate-spin inline-block mr-2">🔄</span>
                                Grafik yükleniyor...
                            </div>
                        </div>
                    )}
                    {error && (
                        <div className="flex items-center justify-center h-full">
                            <div className="text-red-400">
                                ❌ {error}
                            </div>
                        </div>
                    )}
                    {!loading && !error && (
                        <div className="flex flex-col">
                            {/* Main Chart */}
                            <div className="mb-1">
                                <div className="flex items-center gap-4 mb-1">
                                    <span className="text-gray-400 text-sm">Fiyat Grafiği</span>
                                    <span className="text-yellow-400 text-xs">━━ EMA200</span>
                                </div>
                                <div ref={chartContainerRef} className="w-full" style={{ height: chartHeight }} />
                            </div>

                            {/* Resizer */}
                            <div
                                className="h-2 bg-gray-700 hover:bg-purple-600 cursor-row-resize rounded flex items-center justify-center my-1 transition-colors"
                                onMouseDown={(e) => {
                                    e.preventDefault();
                                    const startY = e.clientY;
                                    const startRatio = chartRatio;

                                    const onMouseMove = (e) => {
                                        const delta = e.clientY - startY;
                                        const deltaRatio = delta / totalChartSpace;
                                        const newRatio = Math.max(0.3, Math.min(0.9, startRatio + deltaRatio));
                                        setChartRatio(newRatio);
                                    };

                                    const onMouseUp = () => {
                                        document.removeEventListener('mousemove', onMouseMove);
                                        document.removeEventListener('mouseup', onMouseUp);
                                    };

                                    document.addEventListener('mousemove', onMouseMove);
                                    document.addEventListener('mouseup', onMouseUp);
                                }}
                            >
                                <div className="w-10 h-1 bg-gray-500 rounded" />
                            </div>

                            {/* Indicator Chart (MACD or Stochastic RSI) */}
                            <div>
                                <div className="flex items-center gap-4 mb-1">
                                    {data?.indicators?.stoch_rsi?.length > 0 ? (
                                        <>
                                            <span className="text-gray-400 text-sm">Stochastic RSI</span>
                                            <span className="text-blue-400 text-xs">━━ %K</span>
                                            <span className="text-yellow-400 text-xs">━━ %D</span>
                                            <span className="text-green-400 text-xs">┄┄ 20</span>
                                            <span className="text-red-400 text-xs">┄┄ 80</span>
                                        </>
                                    ) : (
                                        <>
                                            <span className="text-gray-400 text-sm">MACD</span>
                                            <span className="text-blue-400 text-xs">━━ MACD</span>
                                            <span className="text-yellow-400 text-xs">━━ Signal</span>
                                        </>
                                    )}
                                </div>
                                <div ref={indicatorContainerRef} className="w-full" style={{ height: macdHeight }} />
                            </div>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-3 border-t border-gray-700 bg-gray-800/50">
                    <div className="flex items-center justify-between text-xs text-gray-500">
                        <span>Son 50 bar gösteriliyor</span>
                        <span>
                            Güncelleme: {new Date().toLocaleTimeString('tr-TR', {
                                hour: '2-digit',
                                minute: '2-digit',
                                timeZone: 'Europe/Istanbul'
                            })}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
}
