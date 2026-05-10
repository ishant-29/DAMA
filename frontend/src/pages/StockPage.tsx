import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Container, Row, Col, Card, Badge, Table, Button } from 'react-bootstrap';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Brush } from 'recharts';
import { fetchHistorical, analyzeStock, getSectorSentiment, executePaperTrade, getSignalBySymbol } from '../services/api';
import AppNavbar from '../components/Navbar';
import Skeleton from '../components/ui/Skeleton.tsx';
import CountUp from '../components/ui/CountUp.tsx';


const StockPage: React.FC = () => {
    const { symbol } = useParams<{ symbol: string }>();
    const [data, setData] = React.useState<any[]>([]);
    const [signal, setSignal] = React.useState<any>(null);
    const [dbSignal, setDbSignal] = React.useState<any>(null);
    const [loading, setLoading] = React.useState(true);
    const [chartLoading, setChartLoading] = React.useState(true); // independent chart skeleton
    const [tradingLoading, setTradingLoading] = useState(false);
    const [tradeQty, setTradeQty] = useState('');
    const [errorMsg, setErrorMsg] = React.useState<string | null>(null);
    const [sectorRank, setSectorRank] = React.useState<{ rank: number, total: number, name: string } | null>(null);

    // Chart indicator visibility state
    const [visibility, setVisibility] = React.useState({
        price: true,
        ema10: true,
        ema20: true,
        ema50: true,
        darvasHigh: true,
        darvasLow: true
    });
    const [soloMode, setSoloMode] = React.useState(false);

    // Toggle handler
    const toggleIndicator = (key: keyof typeof visibility) => {
        if (soloMode) {
            // Solo mode: show only selected, hide others
            const newVisibility = Object.keys(visibility).reduce((acc, k) => ({
                ...acc,
                [k]: k === key
            }), {} as typeof visibility);
            setVisibility(newVisibility);
        } else {
            // Normal mode: toggle individual
            setVisibility(prev => ({ ...prev, [key]: !prev[key] }));
        }
    };

    const handleSimulateTrade = async () => {
        if (!symbol) return;
        setTradingLoading(true);
        try {
            const qtyParam = tradeQty && !isNaN(Number(tradeQty)) ? Number(tradeQty) : undefined;
            const trade = await executePaperTrade(symbol, qtyParam);
            alert(`Trade Executed!\nSymbol: ${trade.symbol}\nQuantity: ${trade.quantity}\nEntry Price: ₹${trade.entry_price}\nAllocated Capital: ₹${trade.allocated_capital}`);
        } catch (error: any) {
            console.error(error);
            alert(`Failed to execute trade: ${error.response?.data?.detail || error.message}`);
        } finally {
            setTradingLoading(false);
        }
    };

    React.useEffect(() => {
        const loadData = async () => {
            if (!symbol) return;
            try {
                setErrorMsg(null);

                // ── FAST PATH: DB signal read (pure DB query, ~50ms) ──
                const dbSig = await getSignalBySymbol(symbol).catch(() => null);
                if (dbSig) {
                    setDbSignal(dbSig);
                    setSignal({
                        symbol: dbSig.symbol,
                        timestamp: dbSig.timestamp,
                        signal_type: dbSig.signal_type,
                        confidence: dbSig.confidence,
                        reason: dbSig.reason,
                        sector_score: dbSig.sector_score,
                        sector: dbSig.sector || '',
                        is_high_risk: dbSig.reason?.is_high_risk ?? false,
                        vol_valid: dbSig.reason?.vol_valid ?? true,
                    });
                    setLoading(false); // Render page immediately — chart still loading
                }

                // ── PARALLEL SLOW FETCHES ──
                // fetchHistorical: Redis-cached after first visit (instant on repeat)
                // analyzeStock:    returns DB signal fast-path (instant if fresh)
                // getSectorSentiment: cached on backend
                const [histData, signalData, sectorData] = await Promise.all([
                    fetchHistorical(symbol),
                    analyzeStock(symbol),
                    getSectorSentiment(),
                ]);

                // Chart data (60-day window)
                if (Array.isArray(histData)) {
                    setData(histData.slice(-60));
                }
                setChartLoading(false);

                if (signalData) {
                    setSignal(signalData);

                    if (sectorData && signalData.sector) {
                        const sortedSectors = [...sectorData].sort((a, b) => b.score - a.score);
                        const matchIndex = sortedSectors.findIndex(s => s.sector === signalData.sector);
                        if (matchIndex !== -1) {
                            setSectorRank({
                                rank: matchIndex + 1,
                                total: sortedSectors.length,
                                name: signalData.sector
                            });
                        }
                    }
                }
            } catch (e: any) {
                console.error("Failed to load data", e);
                setErrorMsg(e?.message || "Unknown error occurred");
                setChartLoading(false);
            } finally {
                setLoading(false);
            }
        };
        loadData();
    }, [symbol]);

    if (loading) {
        return (
            <div className="min-vh-100 d-flex flex-column">
                <AppNavbar />
                <Container className="p-4" style={{ maxWidth: '1400px' }}>
                    <Skeleton width={200} height={40} className="mb-2" />
                    <Skeleton width={150} height={30} className="mb-5" />
                    <Row>
                        <Col lg={8}><Skeleton height={450} /></Col>
                        <Col lg={4}><Skeleton height={450} /></Col>
                    </Row>
                </Container>
            </div>
        );
    }

    // Show error only if we have neither historical data nor signal
    if ((!data || data.length === 0) && !signal) {
        return (
            <div className="min-vh-100 p-5 text-body text-center animate-fade-in">
                <h3 className="mb-3 text-danger">Data Retrieval Failed</h3>
                <p className="text-muted mb-4">Could not retrieve data for {symbol}</p>
                {errorMsg && (
                    <div className="alert alert-warning d-inline-block px-4 py-2 mb-4" style={{ maxWidth: '600px' }}>
                        <small className="font-monospace text-danger">{errorMsg}</small>
                    </div>
                )}
                <div>
                    <small className="text-secondary">Please check if the backend server is running at <span className="font-monospace">localhost:8090</span></small>
                </div>
                <br />
                <Link to="/" className="btn btn-accent px-4 py-2 text-decoration-none">Return to Nexus</Link>
            </div>
        );
    }

    // If we have signal but no chart data, show signal info only
    const hasChartData = data && data.length > 0;

    // Latest Data (with safe defaults)
    const latestCandle = hasChartData ? data[data.length - 1] : {
        price: signal?.reason?.close || 0,
        ema10: signal?.reason?.ema_10 || 0,
        box_high: signal?.reason?.darvas_high || 0,
        box_low: signal?.reason?.darvas_low || 0
    };
    const currentPrice = latestCandle.price;

    // Status Logic
    let badgeBg = "secondary";
    let displayStatus = "NEUTRAL";
    if (signal?.signal_type === "BUY") { badgeBg = "success"; displayStatus = "BUY SIGNAL ACTIVE"; }
    if (signal?.signal_type === "SELL") { badgeBg = "danger"; displayStatus = "SELL SIGNAL ACTIVE"; }

    // Custom Tooltip for Chart
    const CustomTooltip = ({ active, payload, label }: any) => {
        if (active && payload && payload.length) {
            return (
                <div style={{
                    backgroundColor: 'rgba(255, 255, 255, 0.9)',
                    border: '1px solid rgba(0, 0, 0, 0.05)',
                    backdropFilter: 'blur(10px)',
                    padding: '16px',
                    borderRadius: '12px',
                    boxShadow: '0 10px 40px -10px rgba(0,0,0,0.1)'
                }}>
                    <p className="mb-2 fw-bold text-primary small font-monospace">{label}</p>
                    {payload.map((entry: any) => (
                        <div key={entry.name} className="d-flex align-items-center gap-2 mb-1" style={{ fontSize: '0.85rem' }}>
                            <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: entry.color }}></div>
                            <span className="text-secondary">{entry.name}:</span>
                            <span className="text-primary fw-bold">{entry.value.toFixed(2)}</span>
                        </div>
                    ))}
                </div>
            );
        }
        return null;
    };

    return (
        <div className="min-vh-100 d-flex flex-column">
            <AppNavbar />

            <Container className="p-4 flex-grow-1" style={{ maxWidth: '1400px' }}>
                {/* Header */}
                <div className="d-flex flex-column flex-md-row justify-content-between align-items-start align-items-md-center mb-5 animate-fade-in delay-100">
                    <div>
                        <div className="d-flex align-items-baseline gap-3">
                            <h1 className="display-4 fw-bold text-primary mb-0" style={{ letterSpacing: '-2px' }}>{symbol}</h1>
                            <span className="fs-2 fw-bold text-gradient-accent">
                                ₹<CountUp end={currentPrice} decimals={2} separator="," />
                            </span>
                            <Badge bg={badgeBg} className="align-self-center py-2 px-3 shadow-sm badge-pulse border border-secondary border-opacity-25">{displayStatus}</Badge>
                            
                            {signal?.signal_type === "BUY" && (
                                <div className="d-flex align-items-center ms-2 gap-2">
                                    <input 
                                        type="number" 
                                        placeholder="Qty (auto)" 
                                        className="form-control form-control-sm border-secondary border-opacity-25"
                                        style={{ width: '80px', borderRadius: '20px', backgroundColor: 'rgba(255,255,255,0.5)' }}
                                        value={tradeQty}
                                        onChange={(e) => setTradeQty(e.target.value)}
                                        disabled={tradingLoading}
                                        min="1"
                                        title="Leave empty for auto sizing"
                                    />
                                    <Button 
                                        variant="outline-success" 
                                        className="d-flex align-items-center gap-2 fw-bold rounded-pill shadow-sm"
                                        onClick={handleSimulateTrade}
                                        disabled={tradingLoading}
                                    >
                                        {tradingLoading ? <span className="spinner-border spinner-border-sm" /> : "📊"} 
                                        {tradingLoading ? "Taking Position..." : "Simulate Trade"}
                                    </Button>
                                </div>
                            )}
                        </div>
                        <div className="mt-2 d-flex gap-3 text-secondary small font-monospace">
                            <span>CONFIDENCE: <span className="text-primary fw-bold"><CountUp end={signal?.confidence * 100} decimals={0} suffix="%" /></span></span>
                            <span className="opacity-25">|</span>
                            <span>
                                SECTOR RANK:
                                {sectorRank ? (
                                    <span className="text-primary fw-bold ms-1">
                                        #{sectorRank.rank} <span className="text-secondary fw-normal opacity-75">/ {sectorRank.total} ({sectorRank.name})</span>
                                    </span>
                                ) : (
                                    <span className="text-muted ms-1">#{(signal?.sector_score * 10).toFixed(0)} (Est.)</span>
                                )}
                            </span>
                        </div>
                        {dbSignal && (
                            <div className="mt-2 text-secondary small font-monospace d-flex align-items-center gap-2">
                                <span>LATEST DB SIGNAL: </span>
                                <Badge bg={dbSignal.signal_type === 'BUY' ? 'success' : 'danger'} className="fw-bold px-2">{dbSignal.signal_type}</Badge>
                                <span className="fw-bold">{(dbSignal.confidence * 100).toFixed(0)}% Conf.</span>
                                <span className="opacity-50">({new Date(dbSignal.timestamp).toLocaleDateString()})</span>
                            </div>
                        )}
                    </div>
                    <Link to="/" className="btn btn-glass mt-3 mt-md-0 px-4 py-2 rounded-pill text-primary">
                        &larr; Back to Dashboard
                    </Link>
                </div>

                <Row className="mb-4 g-4">
                    {/* CHART CARD */}
                    {chartLoading ? (
                        <Col lg={8} className="animate-fade-in delay-200">
                            <Card className="h-100 glass-card border-0">
                                <Card.Header className="bg-transparent border-bottom border-secondary border-opacity-10 py-3 px-4 d-flex justify-content-between align-items-center">
                                    <span className="text-primary fw-bold">Price Action Analysis</span>
                                    <Badge bg="light" className="border border-secondary text-secondary fw-normal">Daily TF</Badge>
                                </Card.Header>
                                <Card.Body className="p-4 d-flex align-items-center justify-content-center" style={{ height: '490px' }}>
                                    <div className="w-100">
                                        <Skeleton height={420} />
                                    </div>
                                </Card.Body>
                            </Card>
                        </Col>
                    ) : hasChartData ? (
                        <Col lg={8} className="animate-fade-in delay-200">
                            <Card className="h-100 glass-card border-0">
                                <Card.Header className="bg-transparent border-bottom border-secondary border-opacity-10 py-3 px-4 d-flex justify-content-between align-items-center">
                                    <span className="text-primary fw-bold">Price Action Analysis</span>
                                    <Badge bg="light" className="border border-secondary text-secondary fw-normal">Daily TF</Badge>
                                </Card.Header>

                                {/* Toggle Controls */}
                                <div className="px-4 py-3 border-bottom border-secondary border-opacity-10 bg-light bg-opacity-25">
                                    <div className="d-flex gap-2 flex-wrap align-items-center">
                                        <small className="text-secondary me-1 fw-bold" style={{ fontSize: '0.7rem' }}>INDICATORS:</small>

                                        <button className={`btn btn-sm px-2 py-1 ${visibility.price ? 'btn-success' : 'btn-outline-secondary'}`}
                                            onClick={() => toggleIndicator('price')} style={{ fontSize: '0.7rem' }}>
                                            Price
                                        </button>
                                        <button className={`btn btn-sm px-2 py-1 ${visibility.ema10 ? 'btn-info' : 'btn-outline-secondary'}`}
                                            onClick={() => toggleIndicator('ema10')} style={{ fontSize: '0.7rem' }}>
                                            EMA 10
                                        </button>
                                        <button className={`btn btn-sm px-2 py-1 ${visibility.ema20 ? 'text-white' : 'btn-outline-secondary'}`}
                                            onClick={() => toggleIndicator('ema20')}
                                            style={{ fontSize: '0.7rem', backgroundColor: visibility.ema20 ? '#f59e0b' : 'transparent', borderColor: visibility.ema20 ? '#f59e0b' : '#6c757d' }}>
                                            EMA 20
                                        </button>
                                        <button className={`btn btn-sm px-2 py-1 ${visibility.ema50 ? 'btn-danger' : 'btn-outline-secondary'}`}
                                            onClick={() => toggleIndicator('ema50')} style={{ fontSize: '0.7rem' }}>
                                            EMA 50
                                        </button>
                                        <button className={`btn btn-sm px-2 py-1 ${visibility.darvasHigh ? 'text-white' : 'btn-outline-secondary'}`}
                                            onClick={() => toggleIndicator('darvasHigh')}
                                            style={{ fontSize: '0.7rem', backgroundColor: visibility.darvasHigh ? '#8b5cf6' : 'transparent', borderColor: visibility.darvasHigh ? '#8b5cf6' : '#6c757d' }}>
                                            Darvas High
                                        </button>
                                        <button className={`btn btn-sm px-2 py-1 ${visibility.darvasLow ? 'text-white' : 'btn-outline-secondary'}`}
                                            onClick={() => toggleIndicator('darvasLow')}
                                            style={{ fontSize: '0.7rem', backgroundColor: visibility.darvasLow ? '#8b5cf6' : 'transparent', borderColor: visibility.darvasLow ? '#8b5cf6' : '#6c757d' }}>
                                            Darvas Low
                                        </button>

                                        <div className="ms-auto d-flex align-items-center gap-2">
                                            <small className="text-secondary fw-bold" style={{ fontSize: '0.7rem' }}>SOLO:</small>
                                            <input type="checkbox" checked={soloMode} onChange={(e) => setSoloMode(e.target.checked)}
                                                className="form-check-input" style={{ cursor: 'pointer' }} />
                                        </div>
                                    </div>
                                </div>

                                <Card.Body className="p-4">
                                    <div style={{ width: '100%', height: '450px' }}>
                                        <ResponsiveContainer width="100%" height="100%">
                                            <LineChart data={data}>
                                                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                                                <XAxis dataKey="name" stroke="#94a3b8" tick={{ fill: '#64748b', fontSize: 12 }} minTickGap={40} axisLine={false} tickLine={false} dy={10} />
                                                <YAxis domain={['auto', 'auto']} stroke="#94a3b8" tick={{ fill: '#64748b', fontSize: 12 }} axisLine={false} tickLine={false} dx={-10} />
                                                <Tooltip content={<CustomTooltip />} />
                                                <Legend verticalAlign="top" height={36} iconType="circle" wrapperStyle={{ paddingBottom: '20px' }} />
                                                <Brush dataKey="name" height={30} stroke="#10b981" fill="#f0fdf4" />

                                                {visibility.price && <Line type="monotone" dataKey="price" stroke="#10b981" strokeWidth={2} dot={false} activeDot={{ r: 6, fill: '#10b981', stroke: '#fff' }} name="Price" />}
                                                {visibility.ema10 && <Line type="monotone" dataKey="ema10" stroke="#06b6d4" strokeWidth={1.5} dot={false} strokeDasharray="5 5" name="EMA 10" />}
                                                {visibility.ema20 && <Line type="monotone" dataKey="ema20" stroke="#f59e0b" strokeWidth={1.5} dot={false} strokeDasharray="5 5" name="EMA 20" />}
                                                {visibility.ema50 && <Line type="monotone" dataKey="ema50" stroke="#ef4444" strokeWidth={1.5} dot={false} strokeDasharray="5 5" name="EMA 50" />}
                                                {visibility.darvasHigh && <Line type="step" dataKey="box_high" stroke="#8b5cf6" strokeWidth={1} dot={false} strokeDasharray="3 3" name="Darvas High" />}
                                                {visibility.darvasLow && <Line type="step" dataKey="box_low" stroke="#8b5cf6" strokeWidth={1} dot={false} strokeDasharray="3 3" name="Darvas Low" />}
                                            </LineChart>
                                        </ResponsiveContainer>
                                    </div>
                                </Card.Body>
                            </Card>
                        </Col>
                    ) : (
                        <Col lg={8} className="animate-fade-in delay-200">
                            <Card className="h-100 glass-card border-0">
                                <Card.Body className="p-5 text-center">
                                    <p className="text-muted mb-0">Historical chart data not available</p>
                                </Card.Body>
                            </Card>
                        </Col>
                    )}

                    {/* METRICS CARD */}
                    <Col lg={4} className="animate-fade-in delay-300">
                        <Card className="h-100 glass-card border-0">
                            <Card.Header className="bg-transparent border-bottom border-secondary border-opacity-10 py-3 px-4 text-primary fw-bold">
                                Technical Logic
                            </Card.Header>
                            <Card.Body className="p-0">
                                <Table hover responsive className="mb-0 text-primary align-middle bg-transparent">
                                    <tbody className="bg-transparent">
                                        <tr>
                                            <td className="ps-4 text-secondary border-secondary border-opacity-10">Latest Close</td>
                                            <td className="pe-4 text-end fw-bold fs-5 border-secondary border-opacity-10">₹{latestCandle.price.toFixed(2)}</td>
                                        </tr>
                                        <tr>
                                            <td className="ps-4 text-secondary border-secondary border-opacity-10">EMA 10 Trend</td>
                                            <td className="pe-4 text-end text-info fw-bold border-secondary border-opacity-10">₹{latestCandle.ema10?.toFixed(2) ?? '---'}</td>
                                        </tr>
                                        <tr>
                                            <td className="ps-4 text-secondary border-secondary border-opacity-10">Darvas High</td>
                                            <td className="pe-4 text-end fw-bold border-secondary border-opacity-10" style={{ color: '#8b5cf6' }}>₹{latestCandle.box_high?.toFixed(2) ?? '---'}</td>
                                        </tr>
                                        <tr>
                                            <td className="ps-4 text-secondary border-secondary border-opacity-10">Darvas Low</td>
                                            <td className="pe-4 text-end fw-bold border-secondary border-opacity-10" style={{ color: '#8b5cf6' }}>₹{latestCandle.box_low?.toFixed(2) ?? '---'}</td>
                                        </tr>
                                        <tr>
                                            <td className="ps-4 text-secondary border-secondary border-opacity-10">Volume Strength</td>
                                            <td className="pe-4 text-end border-secondary border-opacity-10">
                                                <Badge bg="light" className="border border-secondary text-secondary">NORMAL</Badge>
                                            </td>
                                        </tr>
                                    </tbody>
                                </Table>

                                <div className="p-4 mt-3" style={{ background: 'rgba(241, 245, 249, 0.5)', borderTop: '1px solid rgba(0,0,0,0.05)' }}>
                                    <h6 className="text-secondary text-uppercase small fw-bold mb-3 tracking-wider">Signal Conditions</h6>
                                    <div className="d-flex flex-column gap-3">
                                        <div className="d-flex justify-content-between align-items-center p-3 rounded-2 shadow-sm" style={{ background: '#ffffff' }}>
                                            <span className="text-primary small">
                                                {signal?.signal_type === 'SELL' ? 'Price < EMA 50' : 'Price > EMA 10'}
                                            </span>
                                            {signal?.reason?.ema_condition ?
                                                <Badge bg="success" className="bg-opacity-10 text-success border border-success border-opacity-25">PASS</Badge> :
                                                <Badge bg="danger" className="bg-opacity-10 text-secondary border border-secondary border-opacity-25">FAIL</Badge>
                                            }
                                        </div>
                                        <div className="d-flex justify-content-between align-items-center p-3 rounded-2 shadow-sm" style={{ background: '#ffffff' }}>
                                            <span className="text-primary small">
                                                {signal?.signal_type === 'SELL' ? 'Darvas Breakdown' : 'Darvas Breakout'}
                                            </span>
                                            {signal?.reason?.darvas_condition ?
                                                <Badge bg="success" className="bg-opacity-10 text-success border border-success border-opacity-25">PASS</Badge> :
                                                <Badge bg="danger" className="bg-opacity-10 text-secondary border border-secondary border-opacity-25">FAIL</Badge>
                                            }
                                        </div>
                                    </div>
                                </div>
                            </Card.Body>
                        </Card>
                    </Col>
                </Row>


            </Container>
        </div>
    );
};

export default StockPage;
