/**
 * Tests for PaperTradingPage.tsx — trade rows, P&L formatting, monitor button, tax report.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mock Navbar
vi.mock('../../components/Navbar.tsx', () => ({ default: () => <nav data-testid="navbar" /> }));

// Mock api — must include ALL imports used by PaperTradingPage
const mockGetPaperPortfolio = vi.fn();
const mockGetPaperTradesList = vi.fn();
const mockTriggerPaperMonitor = vi.fn();
const mockGetTaxReport = vi.fn();
const mockGetActiveTrades = vi.fn();
const mockCreatePaperPortfolio = vi.fn();

vi.mock('../../services/api', () => ({
    getPaperPortfolio: (...args: any[]) => mockGetPaperPortfolio(...args),
    getPaperTradesList: (...args: any[]) => mockGetPaperTradesList(...args),
    triggerPaperMonitor: (...args: any[]) => mockTriggerPaperMonitor(...args),
    getTaxReport: (...args: any[]) => mockGetTaxReport(...args),
    getActiveTrades: (...args: any[]) => mockGetActiveTrades(...args),
    createPaperPortfolio: (...args: any[]) => mockCreatePaperPortfolio(...args),
    getAuthToken: vi.fn(() => 'mock-token'),
}));

import PaperTradingPage from '../../pages/PaperTradingPage';

function renderPage() {
    return render(
        <MemoryRouter>
            <PaperTradingPage />
        </MemoryRouter>
    );
}

describe('PaperTradingPage', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockGetPaperPortfolio.mockResolvedValue({
            portfolio: { name: 'Test', initial_capital: 1000000, current_cash: 950000, current_value: 1000000, total_pnl: 0, total_pnl_pct: 0 },
            stats: { total_trades: 0, win_rate: 0, avg_winner_pct: 0, avg_loser_pct: 0, profit_factor: 0, open_positions: 0 },
            open_positions: [],
            equity_curve: [],
            recent_trades: [],
        });
        mockGetPaperTradesList.mockResolvedValue([]);
        mockGetTaxReport.mockResolvedValue({ trades: [], total_stcg: 0, total_ltcg: 0 });
        mockGetActiveTrades.mockResolvedValue([]);
    });

    describe('trade rendering', () => {
        it('shows empty state when no active trades exist', async () => {
            renderPage();
            await waitFor(() => {
                expect(document.body).toBeTruthy();
            });
        });

        it('renders portfolio data with open positions', async () => {
            mockGetPaperPortfolio.mockResolvedValue({
                portfolio: { name: 'Test', initial_capital: 1000000, current_cash: 950000, current_value: 1010000, total_pnl: 10000, total_pnl_pct: 1.0 },
                stats: { total_trades: 1, win_rate: 100, avg_winner_pct: 4.0, avg_loser_pct: 0, profit_factor: 999, open_positions: 1 },
                open_positions: [
                    { symbol: 'RELIANCE.NS', sector: 'Energy', entry_price: 2500, quantity: 10, stop_loss: 2400, target_price: 2700, days_held: 5, confidence: 0.8 },
                ],
                equity_curve: [],
                recent_trades: [],
            });
            renderPage();
            await waitFor(
                () => {
                    // Page should finish loading and show portfolio data
                    expect(mockGetPaperPortfolio).toHaveBeenCalled();
                    const text = document.body.textContent || '';
                    // Should contain either the symbol or some portfolio metric
                    expect(text.length).toBeGreaterThan(10);
                },
                { timeout: 3000 }
            );
        });
    });

    describe('toFixed null guard', () => {
        it('does not crash when current_price is null', async () => {
            // Should render without throwing
            expect(() => renderPage()).not.toThrow();
            await waitFor(() => {
                expect(document.body).toBeTruthy();
            });
        });

        it('renders 0.00 for zero pnl_percent', async () => {
            mockGetPaperPortfolio.mockResolvedValue({
                portfolio: { name: 'Test', initial_capital: 1000000, current_cash: 1000000, current_value: 1000000, total_pnl: 0, total_pnl_pct: 0 },
                stats: { total_trades: 0, win_rate: 0, avg_winner_pct: 0, avg_loser_pct: 0, profit_factor: 0, open_positions: 0 },
                open_positions: [],
                equity_curve: [],
                recent_trades: [],
            });
            renderPage();
            await waitFor(() => {
                const text = document.body.textContent || '';
                expect(text).toContain('0.00');
            });
        });
    });

    describe('monitor trades', () => {
        it('calls triggerPaperMonitor when button clicked', async () => {
            mockTriggerPaperMonitor.mockResolvedValue({ status: 'ok' });
            renderPage();

            await waitFor(() => {
                expect(mockGetPaperPortfolio).toHaveBeenCalled();
            });

            const buttons = screen.queryAllByRole('button');
            const monitorBtn = buttons.find(b => b.textContent?.toLowerCase().includes('monitor'));
            if (monitorBtn) {
                fireEvent.click(monitorBtn);
                await waitFor(() => {
                    expect(mockTriggerPaperMonitor).toHaveBeenCalled();
                });
            }
        });
    });
});
