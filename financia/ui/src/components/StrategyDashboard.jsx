import { useState, useEffect, useCallback } from 'react';
import SignalsPanel from './SignalsPanel';
import StrategiesPanel from './StrategiesPanel';
import EODAnalysisPanel from './EODAnalysisPanel';
import TradeHistoryPanel from './TradeHistoryPanel';
import ScannerControl from './ScannerControl';
import { useWebSocket } from '../contexts/WebSocketContext';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function StrategyDashboard({ activeTab }) {
    const { scannerStatus, setScannerStatus } = useWebSocket();
    const [strategies, setStrategies] = useState([]);

    // Fetch initial scanner config (only once on mount)
    const fetchScannerConfig = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/strategies/scanner/config`);
            if (res.ok) {
                const data = await res.json();
                setScannerStatus(data);
            }
        } catch (err) {
            console.error('Failed to fetch scanner config:', err);
        }
    }, [setScannerStatus]);

    // Fetch strategies
    const fetchStrategies = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/strategies`);
            if (res.ok) {
                const data = await res.json();
                setStrategies(data);
            }
        } catch (err) {
            console.error('Failed to fetch strategies:', err);
        }
    }, []);

    useEffect(() => {
        fetchScannerConfig();
        fetchStrategies();
        // No more polling - updates come via WebSocket
    }, [fetchScannerConfig, fetchStrategies]);

    const updateScannerConfig = async (updates) => {
        try {
            const res = await fetch(`${API_BASE}/strategies/scanner/config`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updates)
            });
            if (res.ok) {
                const data = await res.json();
                setScannerStatus(data);
            }
        } catch (err) {
            console.error('Failed to update scanner config:', err);
        }
    };

    const triggerScan = async () => {
        if (scannerStatus.is_scanning) return;

        try {
            await fetch(`${API_BASE}/strategies/scanner/scan-now`, { method: 'POST' });
            // Status update will come via WebSocket
        } catch (err) {
            console.error('Failed to trigger scan:', err);
        }
    };

    return (
        <div className="max-w-6xl mx-auto px-8 py-6">
            {/* Scanner Control - Always visible */}
            <ScannerControl
                config={scannerStatus}
                onUpdate={updateScannerConfig}
                onScanNow={triggerScan}
                isScanning={scannerStatus.is_scanning}
            />

            {/* Tab Content */}
            <div className="mt-6">
                {activeTab === 'signals' && (
                    <SignalsPanel strategies={strategies} />
                )}
                {activeTab === 'strategies' && (
                    <StrategiesPanel strategies={strategies} onRefresh={fetchStrategies} />
                )}
                {activeTab === 'eod' && (
                    <EODAnalysisPanel strategies={strategies} />
                )}
                {activeTab === 'history' && (
                    <TradeHistoryPanel strategies={strategies} />
                )}
            </div>
        </div>
    );
}
