import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Container, Row, Col, Card, Badge, Table, ProgressBar, Button, Form, InputGroup } from 'react-bootstrap';
import AppNavbar from '../components/Navbar.tsx';
import { getSignals, type Signal, getSectorReport, getStocksList, getRecentSuggestions } from '../services/api';  // FIXED: S2-04 — removed unused getMarketMood, MarketMood
import { Link } from 'react-router-dom';
import Skeleton from '../components/ui/Skeleton.tsx';
import CountUp from '../components/ui/CountUp.tsx';
import EmptyState from '../components/ui/EmptyState.tsx';
import { Calculator, AlertTriangle } from 'lucide-react';
import { useSignalSocket } from '../hooks/useSignalSocket';
import RegimeBanner from '../components/RegimeBanner';

export default function Dashboard() {
    const [signals, setSignals] = useState<Signal[]>([]);
    const [sectors, setSectors] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchSymbol, setSearchSymbol] = useState("");
    const [allStocks, setAllStocks] = useState<string[]>([]);
    const [suggestions, setSuggestions] = useState<string[]>([]);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [stalenessHours, setStalenessHours] = useState(0);


    const [recentSuggestions, setRecentSuggestions] = useState<any[]>([]);
    const navigate = useNavigate();

    const fetchData = async () => {
        try {
            // Parallel fetch
            const [signalsResult, sectorsData, stocksList, recentSugg] = await Promise.all([
                getSignals(),
                getSectorReport(),
                getStocksList(),
                getRecentSuggestions().catch(() => [])
            ]);
            setSignals(signalsResult.signals);
            setStalenessHours(signalsResult.data_staleness_hours || 0);
            setSectors(sectorsData.all_sectors || []);
            setAllStocks(stocksList);
            setRecentSuggestions(recentSugg);
        } catch (error) {
            if (import.meta.env.DEV) console.error("Failed to fetch dashboard data", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        // Auto-refresh every 30 seconds for overview data
        const interval = setInterval(fetchData, 30000);
        return () => clearInterval(interval);
    }, []);

    // WebSocket: prepend live signals
    useSignalSocket((newSignal: Signal) => {
        setSignals(prev => [newSignal, ...prev]);
    });



    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        if (searchSymbol.trim()) {
            navigate(`/stock/${searchSymbol.trim().toUpperCase()}`);
            setShowSuggestions(false);
        }
    };

    const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const value = e.target.value;
        setSearchSymbol(value);
        if (value.length > 1) {
            const filtered = allStocks.filter(s => s.toLowerCase().includes(value.toLowerCase())).slice(0, 10);
            setSuggestions(filtered);
            setShowSuggestions(true);
        } else {
            setSuggestions([]);
            setShowSuggestions(false);
        }
    };

    const selectSuggestion = (symbol: string) => {
        setSearchSymbol(symbol);
        setSuggestions([]);
        setShowSuggestions(false);
        navigate(`/stock/${symbol}`);
    };

    const buySignals = signals.filter(s => s.signal_type === 'BUY');
    const sellSignals = signals.filter(s => s.signal_type === 'SELL');

    // Derive Top/Bottom Sectors
    // Sort sectors by relative_momentum desc
    const sortedSectors = [...sectors].sort((a, b) => b.relative_momentum - a.relative_momentum);
    const topSectors = sortedSectors.filter(s => s.relative_momentum > 0).slice(0, 2);
    const bottomSectors = sortedSectors.slice(-2).reverse();

    if (loading) return (
        <div className="min-vh-100 d-flex flex-column">
            <AppNavbar />
            <Container className="p-4 flex-grow-1" style={{ maxWidth: '1400px' }}>
                <div className="mb-5 text-center">
                    <Skeleton width={300} height={40} className="mx-auto mb-2" />
                    <Skeleton width={400} height={20} className="mx-auto" />
                </div>
                <div className="row g-4">
                    <div className="col-md-6"><Skeleton height={200} /></div>
                    <div className="col-md-6"><Skeleton height={200} /></div>
                </div>
                <div className="row g-4 mt-4">
                    <div className="col-md-6"><Skeleton height={400} /></div>
                    <div className="col-md-6"><Skeleton height={400} /></div>
                </div>
            </Container>
        </div>
    );

    return (
        <div className="min-vh-100 d-flex flex-column">
            {/* Navigation */}
            <AppNavbar />

            <Container className="p-4 flex-grow-1" style={{ maxWidth: '1400px' }}>
                {/* STALENESS BANNER */}
                {(() => {
                    const now = new Date();
                    const day = now.getDay(); // 0=Sun, 6=Sat
                    const hours = now.getHours();
                    const isWeekend = day === 0 || day === 6;
                    
                    // Indian Standard Time (roughly) - Market close 3:30 PM, Open 9:15 AM
                    const isOffMarketHours = hours < 10 || hours >= 16;
                    
                    const isMondayMorning = day === 1 && hours < 10;
                    const isLongWeekend = stalenessHours > 30 && stalenessHours <= 96;
                    const isWeekendContext = isWeekend || isMondayMorning || isLongWeekend;

                    if (isWeekendContext && stalenessHours > 6 && stalenessHours <= 96) {
                        return null; // Silent check: intentionally hide banners over the weekend
                    }
                    
                    if (isOffMarketHours && stalenessHours > 6 && stalenessHours <= 30) {
                        return (
                            <div className="mb-4 px-4 py-3 rounded-3 d-flex align-items-center gap-2" style={{ background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)' }}>
                                <span style={{ fontSize: '1.2rem' }}>🕒</span>
                                <span className="text-secondary fw-semibold">Market is currently closed. Showing signals from the last session ({Math.round(stalenessHours)}h ago).</span>
                            </div>
                        );
                    }

                    if (stalenessHours > 30) {
                        return (
                            <div className="mb-4 px-4 py-3 rounded-3 d-flex align-items-center gap-2" style={{ background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.4)' }}>
                                <span style={{ fontSize: '1.2rem' }}>🔴</span>
                                <span className="text-danger fw-semibold">Signal data is very old ({Math.round(stalenessHours)} hours). Background sync may have failed.</span>
                            </div>
                        );
                    }
                    if (stalenessHours > 6) {
                        return (
                            <div className="mb-4 px-4 py-3 rounded-3 d-flex align-items-center gap-2" style={{ background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.4)' }}>
                                <span style={{ fontSize: '1.2rem' }}>🔴</span>
                                <span className="text-danger fw-semibold">Signal data is {Math.round(stalenessHours)} hours old. Refresh should happen during market hours.</span>
                            </div>
                        );
                    }
                    if (stalenessHours > 2 && stalenessHours <= 6) {
                        return (
                            <div className="mb-4 px-4 py-3 rounded-3 d-flex align-items-center gap-2" style={{ background: 'rgba(234,179,8,0.15)', border: '1px solid rgba(234,179,8,0.4)' }}>
                                <span style={{ fontSize: '1.2rem' }}>🟡</span>
                                <span className="text-warning fw-semibold">Signal data is {Math.round(stalenessHours)} hours old. Next sync cycle should refresh data.</span>
                            </div>
                        );
                    }
                    if (stalenessHours >= 0 && stalenessHours <= 2) {
                        return (
                            <div className="mb-4 px-4 py-2 rounded-3 d-flex align-items-center gap-2" style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)' }}>
                                <span style={{ fontSize: '1rem' }}>🟢</span>
                                <span className="text-success fw-semibold small">Live — data refreshed recently</span>
                            </div>
                        );
                    }
                    return null;
                })()}

                {/* MARKET REGIME BANNER */}
                <RegimeBanner />

                {/* SEARCH SECTION */}
                <Row className="mb-5 justify-content-center animate-fade-in">
                    <Col md={8} lg={6} className="position-relative">
                        <div className="text-center mb-4">
                            <h2 className="display-5 fw-bold text-primary mb-2">NSE 500 <span className="text-gradient-accent">Signal Engine</span></h2>
                        </div>
                        <Form onSubmit={handleSearch}>
                            <InputGroup className="glass-panel rounded-pill p-1 shadow-card border-0">
                                <Form.Control
                                    placeholder="Search Ticker (e.g. RELIANCE)"
                                    className="text-primary border-0 bg-transparent ps-4 fs-5"
                                    style={{ boxShadow: 'none' }}
                                    value={searchSymbol}
                                    onChange={handleSearchChange}
                                    onFocus={() => { if (searchSymbol.length > 1) setShowSuggestions(true); }}
                                    onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
                                />
                                <Button variant="primary" className="rounded-pill px-5 fw-bold m-1" type="submit">SEARCH</Button>
                            </InputGroup>
                            {showSuggestions && suggestions.length > 0 && (
                                <div className="position-absolute w-100 glass-panel rounded-3 mt-2 overflow-hidden shadow-card" style={{ zIndex: 1000, top: '100%' }}>
                                    {suggestions.map(s => (
                                        <div
                                            key={s}
                                            className="p-3 text-primary cursor-pointer hover-bg-light border-bottom border-secondary-subtle d-flex justify-content-between align-items-center"
                                            style={{ cursor: 'pointer' }}
                                            onMouseDown={() => selectSuggestion(s)}
                                        >
                                            <span className="fw-bold">{s}</span>
                                            <small className="text-secondary">NSE</small>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </Form>
                    </Col>
                </Row>


                {/* SECTOR PERFORMANCE SECTION */}
                <div className="d-flex justify-content-between align-items-end mb-4 animate-fade-in delay-100">
                    <div>
                        <h4 className="text-primary fw-bold mb-1">Market Overview</h4>
                        <p className="text-secondary small mb-0">Sector performance based on 5-day return</p>
                    </div>
                    <div className="d-flex align-items-center gap-3">
                        <div className="d-flex align-items-center gap-2 px-3 py-2 rounded-pill bg-success bg-opacity-10 border border-success border-opacity-20">
                            <span className="position-relative d-flex h-2 w-2" style={{ width: '8px', height: '8px' }}>
                                <span className="animate-ping position-absolute h-100 w-100 rounded-circle bg-success opacity-75"></span>
                                <span className="position-relative inline-flex rounded-circle h-2 w-2 bg-success" style={{ width: '8px', height: '8px' }}></span>
                            </span>
                            <span className="text-success fw-bold small">Autonomous Mode: Active</span>
                        </div>
                    </div>
                </div>

                <Row className="g-4 mb-5 animate-fade-in delay-200">
                    {/* Top Gainers */}
                    <Col md={6}>
                        <Card className="h-100 glass-card border-0">
                            <Card.Header className="bg-transparent border-0 pt-4 px-4 d-flex justify-content-between align-items-center">
                                <strong className="text-success fs-5 d-flex align-items-center gap-2">
                                    <span className="rounded-circle bg-success bg-opacity-10 p-2 d-flex justify-content-center align-items-center" style={{ width: 32, height: 32 }}>📈</span>
                                    Top Gainers
                                </strong>
                            </Card.Header>
                            <Card.Body className="px-4 pb-4 pt-2">
                                <div className="d-flex flex-column gap-3">
                                    {topSectors.map(sec => (
                                        <div key={sec.sector} className="p-3 rounded-3" style={{ background: '#f0fdf4', border: '1px solid #dcfce7' }}>
                                            <div className="d-flex justify-content-between align-items-start">
                                                <div>
                                                    <div className="fw-bold text-dark fs-5">{sec.sector}</div>
                                                    <div className="text-success small mt-1">Strong Momentum</div>
                                                </div>
                                                <div className="text-end">
                                                    <Badge bg="success" className="fs-6 px-3 py-2 rounded-pill mb-1">
                                                        {sec.relative_momentum > 0 ? '+' : ''}<CountUp end={sec.relative_momentum} decimals={2} suffix="%" />
                                                    </Badge>
                                                    <div className="text-muted small">Relative Mom.</div>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                    {topSectors.length === 0 && <span className="text-muted text-center py-4">No sector showing positive momentum</span>}
                                </div>
                            </Card.Body>
                        </Card>
                    </Col>

                    {/* Top Losers */}
                    <Col md={6}>
                        <Card className="h-100 glass-card border-0">
                            <Card.Header className="bg-transparent border-0 pt-4 px-4 d-flex justify-content-between align-items-center">
                                <strong className="text-danger fs-5 d-flex align-items-center gap-2">
                                    <span className="rounded-circle bg-danger bg-opacity-10 p-2 d-flex justify-content-center align-items-center" style={{ width: 32, height: 32 }}>📉</span>
                                    Top Losers
                                </strong>
                            </Card.Header>
                            <Card.Body className="px-4 pb-4 pt-2">
                                <div className="d-flex flex-column gap-3">
                                    {bottomSectors.map(sec => (
                                        <div key={sec.sector} className="p-3 rounded-3" style={{ background: '#fef2f2', border: '1px solid #fee2e2' }}>
                                            <div className="d-flex justify-content-between align-items-start">
                                                <div>
                                                    <div className="fw-bold text-dark fs-5">{sec.sector}</div>
                                                    <div className="text-danger small mt-1">Weak Momentum</div>
                                                </div>
                                                <div className="text-end">
                                                    <Badge bg="danger" className="fs-6 px-3 py-2 rounded-pill mb-1">
                                                        {sec.relative_momentum > 0 ? '+' : ''}<CountUp end={sec.relative_momentum} decimals={2} suffix="%" />
                                                    </Badge>
                                                    <div className="text-muted small">Relative Mom.</div>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                    {bottomSectors.length === 0 && <span className="text-muted text-center py-4">No data available</span>}
                                </div>
                            </Card.Body>
                        </Card>
                    </Col>
                </Row>

                <h4 className="text-primary mb-4 animate-fade-in delay-200">Live Recommendations</h4>
                <Row className="g-4 animate-fade-in delay-300">
                    {/* BUY SIDE */}
                    <Col lg={6}>
                        <Card className="h-100 glass-card border-0">
                            <Card.Header className="d-flex justify-content-between align-items-center bg-transparent border-bottom border-light py-3 px-4">
                                <span className="text-success fw-bold d-flex align-items-center gap-2">🚀 Buy Opportunities</span>
                                <Badge bg="success" pill className="px-3">{buySignals.length}</Badge>
                            </Card.Header>
                            <Card.Body className="p-0">
                                {buySignals.length === 0 ? (
                                    <EmptyState
                                        icon={Calculator}
                                        title="No Buy Signals"
                                        description="Our AI hasn't detected any strong buy opportunities right now. Check back when the market moves!"
                                    />
                                ) : (
                                    <div style={{ maxHeight: '650px', overflowY: 'auto' }}>
                                        <Table responsive hover className="mb-0 align-middle">
                                            <thead className="bg-light sticky-top" style={{ zIndex: 1, backgroundColor: '#f8f9fa' }}>
                                                <tr>
                                                    <th className="bg-transparent text-secondary border-0 ps-4">Symbol</th>
                                                    <th className="bg-transparent text-secondary border-0 text-end">Conf.</th>
                                                    <th className="bg-transparent text-secondary border-0 text-center pe-4">Signals</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {buySignals.map(signal => (
                                                    <SignalRow key={signal.uuid} signal={signal} type="BUY" />
                                                ))}
                                            </tbody>
                                        </Table>
                                    </div>
                                )}
                            </Card.Body>
                        </Card>
                    </Col>

                    {/* SELL SIDE */}
                    <Col lg={6}>
                        <Card className="h-100 glass-card border-0">
                            <Card.Header className="d-flex justify-content-between align-items-center bg-transparent border-bottom border-light py-3 px-4">
                                <span className="text-danger fw-bold d-flex align-items-center gap-2">🔻 Sell Warnings</span>
                                <Badge bg="danger" pill className="px-3">{sellSignals.length}</Badge>
                            </Card.Header>
                            <Card.Body className="p-0">
                                {sellSignals.length === 0 ? (
                                    <EmptyState
                                        icon={AlertTriangle}
                                        title="No Sell Signals"
                                        description="No immediate sell warnings detected relative to current momentum."
                                    />
                                ) : (
                                    <div style={{ maxHeight: '650px', overflowY: 'auto' }}>
                                        <Table responsive hover className="mb-0 align-middle">
                                            <thead className="bg-light sticky-top" style={{ zIndex: 1, backgroundColor: '#f8f9fa' }}>
                                                <tr>
                                                    <th className="bg-transparent text-secondary border-0 ps-4">Symbol</th>
                                                    <th className="bg-transparent text-secondary border-0 text-end">Conf.</th>
                                                    <th className="bg-transparent text-secondary border-0 text-center pe-4">Signals</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {sellSignals.map(signal => (
                                                    <SignalRow key={signal.uuid} signal={signal} type="SELL" />
                                                ))}
                                            </tbody>
                                        </Table>
                                    </div>
                                )}
                            </Card.Body>
                        </Card>
                    </Col>
                </Row>

                {/* RECENT SUGGESTIONS */}
                <h4 className="text-primary mt-5 mb-4 animate-fade-in delay-200">Recent System Suggestions</h4>
                <Row className="g-4 mb-5 animate-fade-in delay-300">
                    <Col lg={12}>
                        <Card className="glass-card border-0">
                            <Card.Body className="p-0">
                                {recentSuggestions.length === 0 ? (
                                    <div className="py-5 text-center text-secondary">No recent suggestions found</div>
                                ) : (
                                    <div style={{ maxHeight: '500px', overflowY: 'auto' }}>
                                        <Table responsive hover className="mb-0 align-middle">
                                            <thead className="bg-light border-bottom border-secondary border-opacity-10 sticky-top" style={{ zIndex: 1, backgroundColor: '#f8f9fa' }}>
                                                <tr>
                                                    <th className="bg-transparent text-secondary border-0 ps-4">Symbol</th>
                                                    <th className="bg-transparent text-secondary border-0 text-center">Action</th>
                                                    <th className="bg-transparent text-secondary border-0 text-end">Conf.</th>
                                                    <th className="bg-transparent text-secondary border-0 text-end pe-4">Timestamp</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {recentSuggestions.map((s, idx) => {
                                                    const statusUpper = (s.status || '').toUpperCase();
                                                    let badgeBg = 'secondary';
                                                    let badgeStyle: React.CSSProperties = {};
                                                    if (statusUpper === 'BUY' || statusUpper === 'BUY ZONE' || statusUpper === 'BUY_ZONE') {
                                                        badgeBg = 'success';
                                                    } else if (statusUpper === 'TARGET HIT' || statusUpper === 'TARGET_HIT') {
                                                        badgeBg = 'info';
                                                    } else if (statusUpper === 'STOP LOSS' || statusUpper === 'STOP_LOSS' || statusUpper === 'SELL') {
                                                        badgeBg = 'danger';
                                                    } else if (statusUpper === 'IGNORED') {
                                                        badgeBg = 'warning';
                                                        badgeStyle = { color: '#000' };
                                                    }
                                                    return (
                                                        <tr key={idx} style={{ cursor: 'pointer' }} onClick={() => navigate(`/stock/${s.symbol}`)}>
                                                            <td className="ps-4 fw-bold text-primary">{s.symbol}</td>
                                                            <td className="text-center">
                                                                <Badge bg={badgeBg} className="px-3 py-1 text-uppercase w-50" style={badgeStyle}>
                                                                    {s.status}
                                                                </Badge>
                                                            </td>
                                                            <td className="text-end font-monospace fw-bold">{((s.confidence ?? 0) * 100).toFixed(0)}%</td>
                                                            <td className="text-end text-secondary pe-4">{new Date(s.recommendation_date).toLocaleDateString()}</td>
                                                        </tr>
                                                    );
                                                })}
                                            </tbody>
                                        </Table>
                                    </div>
                                )}
                            </Card.Body>
                        </Card>
                    </Col>
                </Row>


            </Container>
        </div>
    );
}

function SignalRow({ signal, type }: { signal: Signal, type: 'BUY' | 'SELL' }) {
    const isBuy = type === 'BUY';
    const accentClass = isBuy ? 'text-success' : 'text-danger';

    // Format timestamp
    const date = new Date(signal.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

    return (
        <tr style={{ cursor: 'pointer', borderBottom: '1px solid #f1f5f9' }} onClick={() => { }}>
            <td className="ps-4">
                <Link to={`/stock/${signal.symbol}`} className="text-decoration-none d-block">
                    <div className={`fw-bold ${accentClass} stock-symbol-pill fs-5 hover-bounce`}>{signal.symbol}</div>
                    <div className="text-secondary font-monospace small ps-1">{isBuy ? 'Since ' : ''}{date}</div>
                </Link>
            </td>
            <td className="text-end" style={{ width: '120px' }}>
                <div className="d-flex flex-column align-items-end justify-content-center gap-1">
                    <span className="font-monospace fw-bold text-primary fs-6">{(signal.confidence * 100).toFixed(0)}%</span>
                    <ProgressBar
                        now={signal.confidence * 100}
                        variant={isBuy ? "success" : "danger"}
                        style={{ width: '60px', height: '4px', backgroundColor: '#e2e8f0' }}
                    />
                </div>
            </td>

            <td className="text-center pe-4">
                <div className="d-flex gap-2 justify-content-center">
                    {signal.reason.ema_condition && <Badge bg="light" className="text-primary border border-secondary text-opacity-75 py-2 px-3">EMA</Badge>}
                    {signal.reason.darvas_condition && <Badge bg="light" className="text-warning border border-warning py-2 px-3">BOX</Badge>}
                </div>
            </td>
        </tr>
    );
}
