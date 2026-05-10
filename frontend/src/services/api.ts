import axios from 'axios';
import { APP_CONFIG } from '../config';

// Use environment variable with fallback from centralized config
const API_BASE_URL = APP_CONFIG.apiBaseUrl;

// FIXED: S3-03 — Use localStorage for persistence across reloads
let authToken: string | null = localStorage.getItem('nse_auth_token');

export const setAuthToken = (token: string | null) => {
    authToken = token;
    if (token) {
        localStorage.setItem('nse_auth_token', token);
    } else {
        localStorage.removeItem('nse_auth_token');
    }
};

export const getAuthToken = (): string | null => authToken;

export const clearAuthToken = () => {
    authToken = null;
    localStorage.removeItem('nse_auth_token');
};

const api = axios.create({
    baseURL: API_BASE_URL,
    timeout: APP_CONFIG.apiTimeout,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request interceptor — FIXED: S3-03 — read from memory, not localStorage
api.interceptors.request.use(
    (config) => {
        if (authToken) {
            config.headers.Authorization = `Bearer ${authToken}`;
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// FIXED: S3-02 — Replaced hardcoded admin/admin autoLogin with proper login function
export const login = async (username: string, password: string): Promise<boolean> => {
    try {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        const response = await axios.post(`${API_BASE_URL}/auth/login`, formData, {
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
        });
        const token = response.data.access_token;
        setAuthToken(token);
        return true;
    } catch {
        return false;
    }
};

export const register = async (username: string, password: string): Promise<{ success: boolean; message?: string }> => {
    try {
        const response = await axios.post(`${API_BASE_URL}/auth/register`, {
            username,
            password
        });
        const token = response.data.access_token;
        setAuthToken(token);
        return { success: true };
    } catch (error: any) {
        let message = 'Registration failed. Please try again.';
        if (error.response?.data?.detail) {
            message = error.response.data.detail;
        }
        return { success: false, message };
    }
};

// Response interceptor — FIXED: S6-01 — redirect on persistent 401, S10-02 — no console.log
api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;
        if (error.response) {
            if (import.meta.env.DEV) console.error('API Error:', error.response.status, error.response.data); // FIXED: S10-02

            if (error.response.status === 401 && !originalRequest._retry) {
                // FIXED: S6-01 — on 401, redirect to login instead of auto-login
                clearAuthToken();
                window.location.href = '/login?reason=session_expired';
                return Promise.reject(error);
            }
        } else if (error.request) {
            if (import.meta.env.DEV) console.error('Network error - no response received'); // FIXED: S10-02
        }

        return Promise.reject(error);
    }
);


export interface Signal {
    id: number;
    uuid: string;
    symbol: string;
    timestamp: string;
    signal_type: 'BUY' | 'SELL';
    reason: {
        ema_condition: boolean;
        darvas_condition: boolean;
        trend?: string;
        is_high_risk?: boolean;
    };
    confidence: number;
    sector_score: number;
    model_version: string;
    sector?: string;
}

export interface SignalsResponse {
    total: number;
    count: number;
    page: number;
    per_page: number;
    last_updated: string | null;
    data_staleness_hours: number;
    signals: Signal[];
}

export const getSignals = async (params?: {
    skip?: number;
    limit?: number;
    signal_type?: 'BUY' | 'SELL';
    min_confidence?: number;
}): Promise<{ signals: Signal[]; data_staleness_hours: number }> => {
    const response = await api.get<SignalsResponse>('/signals/today', { params });
    return {
        signals: response.data.signals || [],
        data_staleness_hours: response.data.data_staleness_hours || 0,
    };
};

export const getHighRiskSignals = async (params?: { skip?: number; limit?: number }) => {
    const response = await api.get<SignalsResponse>('/signals/high-risk', { params });
    return response.data.signals || [];
};

// Used for fetching chart data
export const fetchHistorical = async (symbol: string) => {
    const response = await api.get(`/fetch/historical?symbol=${symbol}`);
    return response.data;
};

export interface SectorData {
    sector: string;
    score: number;
    buys: number;
    sells: number;
    total_stocks: number;
    avg_change_percent?: number;
}

export const getSectorSentiment = async () => {
    const response = await api.get<SectorData[]>('/sector/sentiment');
    return response.data;
};

export const triggerUpdate = async () => {
    const response = await api.post('/fetch/update');
    return response.data;
};

export interface AnalysisResult {
    symbol: string;
    timestamp: string;
    signal_type: 'BUY' | 'SELL' | 'NEUTRAL';
    confidence: number;
    reason: any;
    sector_score: number;
    sector: string;
    is_high_risk: boolean;
    vol_valid: boolean;
}

export const analyzeStock = async (symbol: string): Promise<AnalysisResult> => {
    const response = await api.get<AnalysisResult>(`/signals/analyze/${symbol}`);
    return response.data;
};

export const getStocksList = async () => {
    const response = await api.get<string[]>('/fetch/stocks');
    return response.data;
};

export interface SectorStock {
    symbol: string;
    price: number;
    change: number;
}

export const getStocksBySector = async (sectorName: string) => {
    const response = await api.get<SectorStock[]>(`/sector/${encodeURIComponent(sectorName)}/stocks`);
    return response.data;
};

export interface MarketMood {
    mood: string;
    score: number;
    description: string;
}

export const getMarketMood = async () => {
    const response = await api.get<MarketMood>('/analytics/market-mood');
    return response.data;
};


export interface ActiveTrade {
    id: number;
    symbol: string;
    entry_date: string;
    entry_price: number;
    status: string;
    pnl_percent?: number;
    holding_days?: number;
    confidence?: number;
}

export const getActiveTrades = async (params?: { sort_by?: string; limit?: number; min_confidence?: number }) => {
    const response = await api.get<ActiveTrade[]>('/performance/active-trades', { params });
    return response.data;
};


export interface RecentSuggestion {
    id: number;
    symbol: string;
    recommendation_date: string;
    entry_price: number;
    current_price?: number;
    pnl_percent?: number;
    confidence: number;
    status: string;
}

export const getRecentSuggestions = async (days: number = 7) => {
    const response = await api.get<RecentSuggestion[]>('/performance/recent-suggestions', { params: { days } });
    return response.data;
};

// --- Phase 2: Market Regime ---
export const getMarketRegime = async () => {
    const { data } = await api.get('/analytics/market-regime');
    return data;
};

// --- Phase 3: Sector Rotation ---
export const getSectorReport = async () => {
    const { data } = await api.get('/analytics/sectors');
    return data;
};

// --- Phase 5: Backtesting ---
export const runBacktest = async (symbol: string, days: number = 365) => {
    const { data } = await api.get(`/analytics/backtest/${symbol}`, { params: { days } });
    return data;
};

// --- Phase 6: Signal outcome grading ---
export const getSignalGrade = async (signalId: number) => {
    const { data } = await api.get(`/signals/${signalId}/grade`);
    return data;
};

// --- Paper Trading ---
export const getPaperPortfolio = async () => {
    const { data } = await api.get('/paper/portfolio');
    return data;
};

export const getPaperTradesList = async () => {
    const { data } = await api.get('/paper/trades');
    return data;
};

export const createPaperPortfolio = async (name: string = 'Paper Portfolio', capital: number = APP_CONFIG.defaultPaperCapital) => {
    const { data } = await api.post('/paper/portfolio', null, { params: { name, capital } });
    return data;
};

export const executePaperTrade = async (symbol: string, quantity?: number) => {
    const url = quantity ? `/paper/trade/${symbol}?quantity=${quantity}` : `/paper/trade/${symbol}`;
    const { data } = await api.post(url);
    return data;
};

export const closePaperTrade = async (tradeId: number) => {
    const { data } = await api.post(`/paper/trade/${tradeId}/close`);
    return data;
};

export const triggerPaperMonitor = async () => {
    const { data } = await api.post('/paper/monitor');
    return data;
};

// --- News Sentiment ---
export const getNewsSentiment = async (symbol: string) => {
    const { data } = await api.get(`/signals/news/${symbol}`);
    return data;
};

// --- Tax Report ---
export const getTaxReport = async (fy?: string) => {
    const { data } = await api.get('/paper/tax-report', { params: fy ? { financial_year: fy } : {} });
    return data;
};

// --- Health ---
// FIXED: S1-03 — check 'healthy' to match comprehensive health endpoint in main.py
export const getHealthStatus = async () => {
    try {
        const { data } = await api.get('/health');
        return data.status === 'healthy';
    } catch {
        return false;
    }
};

export const getSignalBySymbol = async (symbol: string) => {
    const { data } = await api.get(`/signals/symbol/${symbol}`);
    return data;
};

export const evaluateSignals = async () => {
    const { data } = await api.post('/signals/evaluate');
    return data;
};

export const getSectorMomentum = async () => {
    const { data } = await api.get('/sector/momentum');
    return data;
};

export const getPerformanceSummary = async () => {
    const { data } = await api.get('/performance/summary');
    return data;
};

// FIXED: S1-04 — send all params as query params matching backend route signature
export const runFullBacktest = async (symbol: string, params?: {
    start_date: string;
    end_date: string;
    initial_capital?: number;
    position_size_pct?: number;
    stop_loss_pct?: number;
    take_profit_pct?: number;
}) => {
    const { data } = await api.post('/backtest/run', null, {
        params: { symbol, ...params }
    });
    return data;
};

// --- Auth Profile ---
export interface UserProfile {
    username: string;
    is_admin: boolean;
    created_at: string;
}

export const getCurrentUser = async (): Promise<UserProfile> => {
    const { data } = await api.get<UserProfile>('/auth/me');
    return data;
};

// --- User Settings ---
export interface UserSettings {
    stop_loss_pct: number;
    take_profit_pct: number;
    position_size_pct: number;
    initial_capital: number;
    min_confidence: number;
    max_positions: number;
    kelly_fraction: number;
    commission_rate: number;
}

export const getUserSettings = async (): Promise<UserSettings> => {
    const { data } = await api.get<UserSettings>('/user/settings');
    return data;
};

export const updateUserSettings = async (settings: Partial<UserSettings>): Promise<UserSettings> => {
    const { data } = await api.put<UserSettings>('/user/settings', settings);
    return data;
};

export const resetUserSettings = async (): Promise<UserSettings> => {
    const { data } = await api.delete<UserSettings>('/user/settings');
    return data;
};

// --- System Config (Admin) ---
export interface SystemConfig {
    key: string;
    value: string;
    value_type: 'str' | 'int' | 'float' | 'bool';
    description: string;
    updated_at: string;
    updated_by: string;
    resolved_value: any;
}

export const getConfigs = async (): Promise<SystemConfig[]> => {
    const { data } = await api.get<SystemConfig[]>('/admin/config');
    return data;
};

export const updateConfig = async (key: string, value: string): Promise<any> => {
    const { data } = await api.put(`/admin/config/${key}`, { value });
    return data;
};

export const reloadConfigCache = async (): Promise<void> => {
    await api.post('/admin/config/reload');
};

// --- Market Holidays (Admin) ---
export interface MarketHoliday {
    id: number;
    date: string;
    description: string;
}

export const getHolidays = async (year?: number): Promise<MarketHoliday[]> => {
    const { data } = await api.get<MarketHoliday[]>('/admin/market/holidays', {
        params: year ? { year } : {}
    });
    return data;
};

export const addHoliday = async (date: string, description: string): Promise<void> => {
    await api.post('/admin/market/holidays', { date, description });
};

export const deleteHoliday = async (date: string): Promise<void> => {
    await api.delete(`/admin/market/holidays/${date}`);
};

// --- Stock Universe (Admin) ---
export interface StockUniverseItem {
    id: number;
    symbol: string;
    name: string;
    sector: string;
    industry: string;
    index_name: string;
    is_active: boolean;
}

export const getStockUniverse = async (params?: { skip?: number; limit?: number }): Promise<{ total: number; stocks: StockUniverseItem[] }> => {
    const { data } = await api.get('/admin/stocks', { params });
    return data;
};

export const addStockToUniverse = async (stock: Partial<StockUniverseItem>): Promise<void> => {
    await api.post('/admin/stocks', stock);
};

export const updateStockInUniverse = async (symbol: string, updates: Partial<StockUniverseItem>): Promise<void> => {
    await api.put(`/admin/stocks/${symbol}`, updates);
};

export const reloadStockUniverseCache = async (): Promise<void> => {
    await api.post('/admin/stocks/reload');
};

export const importStocksCSV = async (file: File): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);
    const { data } = await api.post('/admin/stocks/import-csv', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    });
    return data;
};


export default api;
