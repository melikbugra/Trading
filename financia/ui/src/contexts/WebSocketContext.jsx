import React, { createContext, useContext, useEffect, useState, useRef } from 'react';

const WebSocketContext = createContext(null);

export const useWebSocket = () => useContext(WebSocketContext);

export const WebSocketProvider = ({ children }) => {
    const [lastMessage, setLastMessage] = useState(null);
    const [isConnected, setIsConnected] = useState(false);
    const wsRef = useRef(null);

    // Get API Endpoint (Convert http/https to ws/wss)
    const getWsUrl = () => {
        const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        // If API URL is relative or absolute http, convert
        if (apiUrl.startsWith('http')) {
            return apiUrl.replace('http', 'ws') + '/ws';
        }
        // Fallback for production if running on same origin
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${protocol}//${window.location.host}/api/ws`; // Assumption if proxy
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
            } catch (err) {
                console.error("WS Parse Error:", err);
            }
        };

        ws.onclose = () => {
            console.log("WebSocket Disconnected. Reconnecting...");
            setIsConnected(false);
            setTimeout(connect, 3000); // Reconnect after 3s
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
        <WebSocketContext.Provider value={{ lastMessage, isConnected }}>
            {children}
        </WebSocketContext.Provider>
    );
};
