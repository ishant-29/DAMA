import { useEffect, useRef, useCallback } from 'react';
import type { Signal } from '../services/api';
import { getAuthToken } from '../services/api';
import { APP_CONFIG } from '../config';

/**
 * Custom hook that connects to the backend WebSocket and calls `onSignal`
 * whenever a new signal is broadcast. Auto-reconnects on disconnect.
 * FIXED: S3-05 — appends JWT token as query param for WebSocket auth.
 * FIXED: S10-03 — derives WS URL from env var.
 */
export function useSignalSocket(onSignal: (signal: Signal) => void) {
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
    const onSignalRef = useRef(onSignal);
    onSignalRef.current = onSignal;

    const connect = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        const token = getAuthToken();
        if (!token) return; // Don't connect without auth

        // FIXED: S10-03 — derive WebSocket URL from config
        const wsBase = APP_CONFIG.wsUrl;
        const url = `${wsBase}/ws/signals?token=${encodeURIComponent(token)}`;

        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data?.type === 'pong' || data?.type === 'ping') return;
                if (data && data.symbol) {
                    onSignalRef.current(data as Signal);
                }
            } catch {
                // Non-JSON message — ignore
            }
        };

        ws.onclose = () => {
            reconnectTimer.current = setTimeout(connect, APP_CONFIG.wsReconnectDelay);
        };

        ws.onerror = () => {
            ws.close();
        };
    }, []);

    useEffect(() => {
        connect();
        return () => {
            wsRef.current?.close();
            if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
        };
    }, [connect]);
}
