import React, { createContext, useContext, useEffect, useState, useRef } from 'react';

const WebSocketContext = createContext(null);

export const useWebSocket = () => useContext(WebSocketContext);

export const WebSocketProvider = ({ children }) => {
    const [lastMessage, setLastMessage] = useState(null);
    const [isConnected, setIsConnected] = useState(false);
    const [activeScans, setActiveScans] = useState([]);
    const [scannerStatus, setScannerStatus] = useState({
        is_running: false,
        is_scanning: false,
        scan_interval_minutes: 5,
        last_scan_at: null
    });
    const [activeSignals, setActiveSignals] = useState([]);
    const wsRef = useRef(null);

    // Get API Endpoint (Convert http/https to ws/wss)
    const getWsUrl = () => {
        const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        if (apiUrl.startsWith('http')) {
            return apiUrl.replace('http', 'ws') + '/ws';
        }
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${protocol}//${window.location.host}/api/ws`;
    };

    const connect = () => {
        const url = getWsUrl();
        console.log("Connecting to WS:", url);

        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
            console.log("WebSocket Connected");
            setIsConnected(true);
        };

        ws.onmessage = (event) => {
            try {
                const updatedData = JSON.parse(event.data);
                setLastMessage(updatedData);

                if (updatedData.type === 'scanner_status') {
                    setScannerStatus(updatedData.data);
                } else if (updatedData.type === 'signals_update') {
                    setActiveSignals(updatedData.data);
                } else if (updatedData.type === 'SCAN_STARTED') {
                    const m = updatedData.data.market;
                    if (m) setActiveScans(prev => [...new Set([...prev, m])]);
                } else if (updatedData.type === 'SCAN_FINISHED') {
                    const m = updatedData.data.market;
                    if (m) setActiveScans(prev => prev.filter(x => x !== m));
                }
            } catch (err) {
                console.error("WS Parse Error:", err);
            }
        };

        ws.onclose = () => {
            console.log("WebSocket Disconnected. Reconnecting...");
            setIsConnected(false);
            setTimeout(connect, 3000);
        };

        ws.onerror = (err) => {
            console.error("WebSocket Error:", err);
            ws.close();
        };
    };

    useEffect(() => {
        connect();
        return () => {
            if (wsRef.current) wsRef.current.close();
        };
    }, []);

    return (
        <WebSocketContext.Provider value={{ lastMessage, isConnected, activeScans, scannerStatus, setScannerStatus, activeSignals }}>
            {children}
        </WebSocketContext.Provider>
    );
};
