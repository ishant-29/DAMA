import React, { useEffect, useState } from 'react';
import { Container, Row, Col, Card, Badge, Modal } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import AppNavbar from '../components/Navbar.tsx';
import { getSectorSentiment, getSectorMomentum, type SectorData } from '../services/api';
import Skeleton from '../components/ui/Skeleton.tsx';
import CountUp from '../components/ui/CountUp.tsx';

const Heatmap: React.FC = () => {
    const [sectors, setSectors] = useState<SectorData[]>([]);
    const [loading, setLoading] = useState<boolean>(true);
    const navigate = useNavigate();

    const [error, setError] = useState<string | null>(null);

    const [momentum, setMomentum] = useState<{ top_gainers: any[], top_losers: any[] }>({ top_gainers: [], top_losers: [] });

    const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
    const [isPolling, setIsPolling] = useState(false);

    const loadData = async (isPoll: boolean = false) => {
        if (!isPoll) setLoading(true);
        setIsPolling(true);
        try {
            const [data, momentumData] = await Promise.all([
                getSectorSentiment(),
                getSectorMomentum()
            ]);

            if (Array.isArray(data)) {
                const sanitizedData = data.map(sec => ({
                    ...sec,
                    score: Number.isFinite(sec.score) ? sec.score : 0,
                    buys: Number.isFinite(sec.buys) ? sec.buys : 0,
                    sells: Number.isFinite(sec.sells) ? sec.sells : 0,
                    avg_change_percent: Number.isFinite(sec.avg_change_percent) ? sec.avg_change_percent : 0
                }));
                setSectors(sanitizedData);
            }
            setMomentum(momentumData);
            setLastUpdated(new Date());
            setError(null);
        } catch (err) {
            console.error("Failed to load sector data", err);
            setError("Failed to load sector data. Please try again later.");
        } finally {
            if (!isPoll) setLoading(false);
            setTimeout(() => setIsPolling(false), 2000);
        }
    };

    useEffect(() => {
        loadData();
        const interval = setInterval(() => loadData(true), 30000);
        return () => clearInterval(interval);
    }, []);



    const [selectedSector, setSelectedSector] = useState<string | null>(null);
    const [sectorStocks, setSectorStocks] = useState<any[]>([]);
    const [showModal, setShowModal] = useState(false);
    const [modalLoading, setModalLoading] = useState(false);

    const handleSectorClick = async (sectorName: string) => {
        setSelectedSector(sectorName);
        setShowModal(true);
        setModalLoading(true);
        try {
            const stocks = await import('../services/api').then(m => m.getStocksBySector(sectorName));
            setSectorStocks(stocks);
        } catch (e) {
            console.error(e);
        } finally {
            setModalLoading(false);
        }
    };

    const getCardStyle = (score: number) => {
        // Score is avg_change_percent
        if (score >= 2.0) return { borderLeft: '4px solid #059669', bg: '#d1fae5' }; // Emerald 100
        if (score > 0) return { borderLeft: '4px solid #10b981', bg: '#ecfdf5' }; // Emerald 50
        if (score < -2.0) return { borderLeft: '4px solid #dc2626', bg: '#fee2e2' }; // Red 100
        if (score < 0) return { borderLeft: '4px solid #ef4444', bg: '#fef2f2' }; // Red 50
        return { borderLeft: '4px solid #94a3b8', bg: '#f8fafc' }; // Slate 50
    };

    return (
        <div className="min-vh-100 d-flex flex-column">
            <AppNavbar />
            <Container className="py-4 flex-grow-1" style={{ maxWidth: '1400px' }}>
                <div className="mb-5 text-center animate-fade-in">
                    <div className="d-flex justify-content-center align-items-center gap-2 mb-2">
                        <Badge bg="success" className={`rounded-pill px-3 py-2 badge-pulse-green ${isPolling ? 'opacity-100' : 'opacity-75'}`} style={{ fontSize: '0.7rem' }}>
                            <span className="me-1">●</span> LIVE
                        </Badge>
                        <small className="text-secondary font-monospace" style={{ fontSize: '0.75rem' }}>
                            Last sync: {lastUpdated.toLocaleTimeString()}
                        </small>
                    </div>
                    <h2 className="display-5 fw-bold text-primary">Sector <span className="text-gradient-accent">Heatmap</span></h2>
                    <p className="text-secondary">Real-time sector rotation and momentum analysis (Auto-refresh: 30s)</p>
                </div>

                {error && (
                    <div className="alert alert-danger text-center mb-4" role="alert">
                        {error}
                    </div>
                )}

                {loading ? (
                    <Row xs={1} md={3} lg={4} className="g-4">
                        {[...Array(8)].map((_, i) => (
                            <Col key={i}>
                                <Card className="h-100 border-0 shadow-sm glass-card">
                                    <Card.Body className="p-4">
                                        <Skeleton width={120} height={24} className="mb-3" />
                                        <div className="d-flex justify-content-between mb-2">
                                            <Skeleton width={60} height={20} />
                                            <Skeleton width={60} height={20} />
                                        </div>
                                        <div className="mt-3 border-top pt-3">
                                            <Skeleton width={100} height={16} />
                                        </div>
                                    </Card.Body>
                                </Card>
                            </Col>
                        ))}
                    </Row>
                ) : (
                    <Row xs={1} md={3} lg={4} className="g-4 animate-fade-in delay-100">
                        {sectors.length === 0 && !loading && !error && (
                            <Col xs={12}>
                                <div className="text-center p-5 text-muted glass-card rounded-3">
                                    <h4>No Sector Data Available</h4>
                                    <p>Check back later once the market is active.</p>
                                </div>
                            </Col>
                        )}
                        {sectors.map((sec) => {
                            const style = getCardStyle(sec.score); // Use Score (Performance)
                            return (
                                <Col key={sec.sector}>
                                    <Card
                                        className={`h-100 border-0 glass-card hover-glow ${isPolling ? 'flash-update' : ''}`}
                                        style={{
                                            cursor: 'pointer',
                                            background: style.bg,
                                            borderLeft: style.borderLeft
                                        }}
                                        onClick={() => handleSectorClick(sec.sector)}
                                    >
                                        <Card.Body className="d-flex flex-column justify-content-between p-4">
                                            <div>
                                                <div className="d-flex justify-content-between align-items-start mb-3">
                                                    <Card.Title className="fw-bold fs-5 text-primary mb-0">{sec.sector}</Card.Title>
                                                    {sec.buys - sec.sells > 0 ?
                                                        <span className="text-success fs-5">↗</span> :
                                                        (sec.buys - sec.sells < 0 ? <span className="text-danger fs-5">↘</span> : <span className="text-secondary">−</span>)
                                                    }
                                                </div>
                                                <div className="d-flex justify-content-between mb-2 small text-secondary fw-bold text-uppercase tracking-wider">
                                                    <span>Buys: <span className="text-success"><CountUp end={sec.buys} duration={1000} /></span></span>
                                                    <span>Sells: <span className="text-danger"><CountUp end={sec.sells} duration={1000} /></span></span>
                                                </div>
                                                <div className="d-flex justify-content-between mb-2">
                                                    <span className="small text-secondary fw-bold">5D Return</span>
                                                    <span className={`fw-bold ${sec.score >= 0 ? 'text-success' : 'text-danger'}`}>
                                                        {sec.score > 0 ? '+' : ''}{sec.score.toFixed(2)}%
                                                    </span>
                                                </div>
                                            </div>
                                            <div className="mt-3 pt-3 border-top border-secondary border-opacity-10">
                                                <div className="d-flex justify-content-between align-items-center">
                                                    <small className="text-secondary">
                                                        {sec.total_stocks} stocks
                                                    </small>
                                                    <Badge bg={sec.buys - sec.sells > 0 ? "success" : (sec.buys - sec.sells < 0 ? "danger" : "secondary")}
                                                        className="bg-opacity-10 text-body border border-opacity-25 px-2 py-1">
                                                        Net: {sec.buys - sec.sells > 0 ? '+' : ''}{sec.buys - sec.sells}
                                                    </Badge>
                                                </div>
                                            </div>
                                        </Card.Body>
                                    </Card>
                                </Col>
                            );
                        })}
                    </Row>
                )}

                {/* SECTOR MOMENTUM TABLE */}
                <Row className="mt-5 mb-4 animate-fade-in delay-200">
                    <Col lg={12}>
                        <h4 className="text-primary mb-4 fw-bold">Top Momentum Sectors</h4>
                        <Card className="glass-card border-0">
                            <Card.Body className="p-0">
                                {momentum.top_gainers.length === 0 && momentum.top_losers.length === 0 ? (
                                    <div className="py-5 text-center text-secondary">No momentum data available</div>
                                ) : (
                                    <div className="table-responsive">
                                        <table className="table table-hover mb-0 align-middle">
                                            <thead className="bg-light">
                                                <tr>
                                                    <th className="bg-transparent text-secondary border-0 ps-4">Sector</th>
                                                    <th className="bg-transparent text-secondary border-0 text-end pe-4">Momentum Score</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {momentum.top_gainers.length > 0 && (
                                                    <tr>
                                                        <td colSpan={2} className="bg-light text-success fw-bold ps-4 py-2 small text-uppercase">Top Gainers</td>
                                                    </tr>
                                                )}
                                                {momentum.top_gainers.map((m, i) => (
                                                    <tr key={`gainer-${i}`}>
                                                        <td className="ps-4 fw-bold text-primary">{m.sector}</td>
                                                        <td className="text-end fw-bold pe-4 text-success">
                                                            {m.avg_return !== undefined ? m.avg_return.toFixed(2) : (m.relative_momentum !== undefined ? m.relative_momentum.toFixed(2) : 0)}%
                                                        </td>
                                                    </tr>
                                                ))}
                                                {momentum.top_losers.length > 0 && (
                                                    <tr>
                                                        <td colSpan={2} className="bg-light text-danger fw-bold ps-4 py-2 small text-uppercase mt-2 border-top">Top Losers</td>
                                                    </tr>
                                                )}
                                                {momentum.top_losers.map((m, i) => (
                                                    <tr key={`loser-${i}`}>
                                                        <td className="ps-4 fw-bold text-primary">{m.sector}</td>
                                                        <td className="text-end fw-bold pe-4 text-danger">
                                                            {m.avg_return !== undefined ? m.avg_return.toFixed(2) : (m.relative_momentum !== undefined ? m.relative_momentum.toFixed(2) : 0)}%
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </Card.Body>
                        </Card>
                    </Col>
                </Row>
            </Container>

            {/* SECTOR DETAIL MODAL */}
            <Modal
                show={showModal}
                onHide={() => setShowModal(false)}
                centered
                size="lg"
                contentClassName="glass-panel border-0 shadow-lg"
                backdropClassName="backdrop-blur"
            >
                <Modal.Header closeButton className="border-bottom border-secondary border-opacity-10">
                    <Modal.Title className="text-primary fw-bold">
                        {selectedSector} <span className="text-gradient-accent fw-normal fs-5 ps-2">Overview</span>
                    </Modal.Title>
                </Modal.Header>
                <Modal.Body className="p-0" style={{ maxHeight: '70vh', overflowY: 'auto' }}>
                    {modalLoading ? (
                        <div className="p-4">
                            {[1, 2, 3, 4, 5].map(i => (
                                <div key={i} className="d-flex justify-content-between mb-3">
                                    <Skeleton width={100} height={20} />
                                    <Skeleton width={80} height={20} />
                                    <Skeleton width={60} height={20} />
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="table-responsive">
                            <table className="table table-hover mb-0 align-middle">
                                <thead className="sticky-top" style={{ backgroundColor: 'rgba(255,255,255,0.95)', backdropFilter: 'blur(5px)' }}>
                                    <tr>
                                        <th className="ps-4 bg-transparent text-secondary border-bottom border-secondary border-opacity-10">Symbol</th>
                                        <th className="text-end bg-transparent text-secondary border-bottom border-secondary border-opacity-10">Price</th>
                                        <th className="text-end pe-4 bg-transparent text-secondary border-bottom border-secondary border-opacity-10">5D Change</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {sectorStocks.map((stock, idx) => (
                                        <tr
                                            key={stock.symbol}
                                            style={{ cursor: 'pointer', animationDelay: `${idx * 50}ms` }}
                                            className="animate-fade-in"
                                            onClick={() => navigate(`/stock/${stock.symbol}`)}
                                        >
                                            <td className="ps-4">
                                                <div className="fw-bold text-primary hover-bounce" style={{ display: 'inline-block' }}>{stock.symbol.replace('.NS', '')}</div>
                                            </td>
                                            <td className="text-end text-secondary fw-bold">₹{stock.price.toFixed(2)}</td>
                                            <td className={`text-end pe-4 fw-bold ${stock.change >= 0 ? 'text-success' : 'text-danger'}`}>
                                                <span className={`badge ${stock.change >= 0 ? 'bg-success' : 'bg-danger'} bg-opacity-10 ${stock.change >= 0 ? 'text-success' : 'text-danger'} border border-opacity-25 px-2`}>
                                                    {stock.change > 0 ? '+' : ''}{stock.change.toFixed(2)}%
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                    {sectorStocks.length === 0 && (
                                        <tr><td colSpan={3} className="text-center p-5 text-muted">No stock data available</td></tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    )}
                </Modal.Body>
            </Modal>
        </div>
    );
};

export default Heatmap;
