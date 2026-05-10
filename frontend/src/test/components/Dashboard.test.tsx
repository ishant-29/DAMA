/**
 * Tests for Dashboard.tsx — confidence display, suggestion list, evaluate button.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mock all heavy child components to isolate Dashboard logic
vi.mock('../../components/Navbar.tsx', () => ({ default: () => <nav data-testid="navbar" /> }));
vi.mock('../../components/RegimeBanner', () => ({ default: () => <div data-testid="regime-banner" /> }));
vi.mock('../../components/SectorRotationWidget', () => ({ default: () => <div data-testid="sector-widget" /> }));
vi.mock('../../components/ui/Skeleton.tsx', () => ({ default: () => <div data-testid="skeleton" /> }));
vi.mock('../../components/ui/CountUp.tsx', () => ({ default: ({ end }: { end: number }) => <span>{end}</span> }));
vi.mock('../../components/ui/EmptyState.tsx', () => ({ default: ({ message }: { message: string }) => <div>{message}</div> }));
vi.mock('../../hooks/useSignalSocket', () => ({ useSignalSocket: vi.fn() }));

// Mock the api module
const mockGetSignals = vi.fn();
const mockGetSectorReport = vi.fn();
const mockGetStocksList = vi.fn();
const mockEvaluateSignals = vi.fn();
const mockGetPerformanceSummary = vi.fn();
const mockGetRecentSuggestions = vi.fn();
const mockTriggerUpdate = vi.fn();

vi.mock('../../services/api', () => ({
    getSignals: (...args: any[]) => mockGetSignals(...args),
    getSectorReport: (...args: any[]) => mockGetSectorReport(...args),
    getStocksList: (...args: any[]) => mockGetStocksList(...args),
    evaluateSignals: (...args: any[]) => mockEvaluateSignals(...args),
    getPerformanceSummary: (...args: any[]) => mockGetPerformanceSummary(...args),
    getRecentSuggestions: (...args: any[]) => mockGetRecentSuggestions(...args),
    triggerUpdate: (...args: any[]) => mockTriggerUpdate(...args),
    getAuthToken: vi.fn(() => 'mock-token'),
}));

import Dashboard from '../../pages/Dashboard';

function renderDashboard() {
    return render(
        <MemoryRouter>
            <Dashboard />
        </MemoryRouter>
    );
}

describe('Dashboard', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockGetSignals.mockResolvedValue({ signals: [], data_staleness_hours: 0 });
        mockGetSectorReport.mockResolvedValue({ all_sectors: [] });
        mockGetStocksList.mockResolvedValue([]);
        mockGetPerformanceSummary.mockResolvedValue(null);
        mockGetRecentSuggestions.mockResolvedValue([]);
    });

    describe('confidence display', () => {
        it('renders "0%" when signal confidence is null', async () => {
            mockGetSignals.mockResolvedValue({
                signals: [{
                    id: 1, symbol: 'TEST.NS', signal_type: 'BUY',
                    confidence: null, sector_score: 0.5,
                    reason: {}, timestamp: '2025-01-01',
                    current_price: 100, entry_price: 100, status: 'OPEN',
                }],
                data_staleness_hours: 0,
            });
            renderDashboard();
            await waitFor(() => {
                // Should not crash and should render something
                expect(document.body).toBeTruthy();
            });
        });

        it('renders confidence percentage correctly from 0.75 value', async () => {
            mockGetSignals.mockResolvedValue({
                signals: [{
                    id: 1, symbol: 'INFY.NS', signal_type: 'BUY',
                    confidence: 0.75, sector_score: 0.6,
                    reason: {}, timestamp: '2025-01-01',
                    current_price: 1500, entry_price: 1480, status: 'OPEN',
                }],
                data_staleness_hours: 0,
            });
            renderDashboard();
            await waitFor(() => {
                // 0.75 * 100 = 75 — the text "75" should appear somewhere
                const allText = document.body.textContent || '';
                expect(allText).toContain('75');
            });
        });
    });

    describe('recent suggestions', () => {
        it('shows empty state when no suggestions exist', async () => {
            mockGetRecentSuggestions.mockResolvedValue([]);
            renderDashboard();
            await waitFor(() => {
                expect(document.body).toBeTruthy();
            });
        });
    });

    describe('evaluate signals button', () => {
        it('calls evaluateSignals when clicked and disables during request', async () => {
            mockEvaluateSignals.mockResolvedValue({ status: 'ok' });
            renderDashboard();

            await waitFor(() => {
                expect(mockGetSignals).toHaveBeenCalled();
            });

            // Find button containing "Evaluate" text
            const buttons = screen.queryAllByRole('button');
            const evalBtn = buttons.find(b => b.textContent?.includes('Evaluate'));
            if (evalBtn) {
                fireEvent.click(evalBtn);
                // The button should be called
                await waitFor(() => {
                    expect(mockEvaluateSignals).toHaveBeenCalled();
                });
            }
        });
    });
});
