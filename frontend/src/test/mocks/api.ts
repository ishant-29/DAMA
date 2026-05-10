/**
 * Shared API mocks for all frontend tests.
 * Import and call vi.mock('../services/api', () => apiMocks) in test files.
 */
import { vi } from 'vitest';

export const mockApi = {
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
  login: vi.fn(),
  register: vi.fn(),
  getAuthToken: vi.fn(() => 'mock-jwt-token'),
  setAuthToken: vi.fn(),
  clearAuthToken: vi.fn(),
  getSignals: vi.fn(() => Promise.resolve({ signals: [], data_staleness_hours: 0 })),
  getHighRiskSignals: vi.fn(() => Promise.resolve([])),
  getSectorSentiment: vi.fn(() => Promise.resolve([])),
  triggerUpdate: vi.fn(() => Promise.resolve({ status: 'ok' })),
  analyzeStock: vi.fn(),
  getStocksList: vi.fn(() => Promise.resolve([])),
  getMarketMood: vi.fn(() => Promise.resolve({ mood: 'NEUTRAL', score: 50, description: 'Test' })),
  getActiveTrades: vi.fn(() => Promise.resolve([])),
  getRecentSuggestions: vi.fn(() => Promise.resolve([])),
  getMarketRegime: vi.fn(() => Promise.resolve({})),
  getSectorReport: vi.fn(() => Promise.resolve({ all_sectors: [] })),
  runBacktest: vi.fn(),
  getSignalGrade: vi.fn(),
  getPaperPortfolio: vi.fn(() => Promise.resolve({})),
  getPaperTradesList: vi.fn(() => Promise.resolve([])),
  createPaperPortfolio: vi.fn(),
  executePaperTrade: vi.fn(),
  triggerPaperMonitor: vi.fn(),
  getNewsSentiment: vi.fn(() => Promise.resolve({})),
  getTaxReport: vi.fn(() => Promise.resolve({})),
  getHealthStatus: vi.fn(() => Promise.resolve(true)),
  evaluateSignals: vi.fn(() => Promise.resolve({})),
  getPerformanceSummary: vi.fn(() => Promise.resolve(null)),
  fetchHistorical: vi.fn(),
  getStocksBySector: vi.fn(),
  getSignalBySymbol: vi.fn(),
  getSectorMomentum: vi.fn(),
  runFullBacktest: vi.fn(),
};
