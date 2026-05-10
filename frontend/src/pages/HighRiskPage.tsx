import { useState, useEffect } from 'react';
import { Container, Card, Badge, Table, ProgressBar } from 'react-bootstrap';
import AppNavbar from '../components/Navbar';
import { getHighRiskSignals, type Signal } from '../services/api';
import { Link } from 'react-router-dom';
import Skeleton from '../components/ui/Skeleton';
import EmptyState from '../components/ui/EmptyState';
import { AlertTriangle, Info } from 'lucide-react';

export default function HighRiskPage() {
    const [signals, setSignals] = useState<Signal[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetch = async () => {
            try {
                const data = await getHighRiskSignals();
                setSignals(data);
            } catch (error) {
                console.error("Failed to fetch high risk signals", error);
            } finally {
                setLoading(false);
            }
        };
        fetch();
    }, []);

    return (
        <div className="min-vh-100 d-flex flex-column">
            <AppNavbar />
            <Container className="py-4 flex-grow-1" style={{ maxWidth: '1400px' }}>
                <div className="mb-5 text-center animate-fade-in">
                    <h2 className="display-5 fw-bold text-warning">High Risk <span className="text-secondary opacity-75">Opportunities</span></h2>
                    <p className="text-secondary mx-auto" style={{ maxWidth: '600px' }}>
                        Trades that meet technical criteria (Breakouts & EMA Trends) but have <strong>Low AI Confidence</strong>.
                        <br /><span className="text-danger fw-bold">Make your own judgement. Higher Volatility Expected.</span>
                    </p>
                </div>

                {loading ? (
                    <div className="p-4"><Skeleton height={300} /></div>
                ) : (
                    <Card className="border-0 shadow-lg glass-card animate-slide-up">
                        <Card.Header className="bg-warning bg-opacity-10 border-bottom border-warning border-opacity-25 py-3 px-4">
                            <div className="d-flex align-items-center gap-2 text-warning fw-bold">
                                <AlertTriangle size={20} />
                                <span>High Risk / Low Confidence Signals</span>
                                <Badge bg="warning" text="dark" pill className="ms-2">{signals.length}</Badge>
                            </div>
                        </Card.Header>
                        <Card.Body className="p-0">
                            {signals.length === 0 ? (
                                <EmptyState
                                    icon={Info}
                                    title="No High Risk Signals"
                                    description="No signals found in the high risk zone today."
                                />
                            ) : (
                                <div className="table-responsive custom-scrollbar" style={{ maxHeight: '500px', overflowY: 'auto' }}>
                                    <Table hover className="mb-0 align-middle">
                                        <thead style={{ position: 'sticky', top: 0, zIndex: 1, background: '#fcfcfd', boxShadow: '0 2px 4px rgba(0,0,0,0.04)' }}>
                                            <tr>
                                                <th className="ps-4 border-0 text-secondary py-3">Symbol</th>
                                                <th className="text-end border-0 text-secondary py-3">Signal</th>
                                                <th className="text-end border-0 text-secondary py-3">AI Conf.</th>
                                                <th className="text-center border-0 text-secondary py-3">Criteria</th>
                                                <th className="text-end pe-4 border-0 text-secondary py-3">Date</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                        {signals.map(s => (
                                            <tr key={s.uuid}>
                                                <td className="ps-4">
                                                    <Link to={`/stock/${s.symbol}`} className="text-decoration-none fw-bold fs-5 text-dark hover-primary-text">
                                                        {s.symbol}
                                                    </Link>
                                                </td>
                                                <td className="text-end">
                                                    <Badge bg={s.signal_type === 'BUY' ? 'success' : 'danger'} className="px-3 py-2 bg-opacity-75">
                                                        {s.signal_type}
                                                    </Badge>
                                                </td>
                                                <td className="text-end">
                                                    <div className="d-flex flex-column align-items-end">
                                                        <span className="fw-bold text-warning">{(s.confidence * 100).toFixed(0)}%</span>
                                                        <ProgressBar
                                                            now={s.confidence * 100}
                                                            variant="warning"
                                                            style={{ width: '60px', height: '4px' }}
                                                        />
                                                    </div>
                                                </td>
                                                <td className="text-center">
                                                    <div className="d-flex gap-2 justify-content-center">
                                                        {s.reason.ema_condition && <Badge bg="light" text="dark" className="border">EMA Trend</Badge>}
                                                        {s.reason.darvas_condition && <Badge bg="light" text="dark" className="border">Box Break</Badge>}
                                                    </div>
                                                </td>
                                                <td className="text-end pe-4 text-secondary font-monospace">
                                                    {new Date(s.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                    </Table>
                                </div>
                            )}
                        </Card.Body>
                    </Card>
                )}
            </Container>
        </div>
    );
}
