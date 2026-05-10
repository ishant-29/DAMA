import { useState, useEffect, useRef } from 'react';
import { Container, Row, Col, Card, Tabs, Tab, Table, Button, Form, Badge, Alert, Spinner } from 'react-bootstrap';
import AppNavbar from '../components/Navbar';
import { 
    getConfigs, updateConfig, reloadConfigCache, type SystemConfig,
    getHolidays, addHoliday, deleteHoliday, type MarketHoliday,
    getStockUniverse, updateStockInUniverse, reloadStockUniverseCache, importStocksCSV, type StockUniverseItem
} from '../services/api';
import { Shield, Settings, Calendar, Database, Trash2, Plus, RefreshCw, Upload, Search, CheckCircle, XCircle } from 'lucide-react';

export default function AdminPage() {
    return (
        <>
            <AppNavbar />
            <Container className="py-5">
                <div className="d-flex align-items-center mb-4">
                    <div className="p-2 bg-danger bg-opacity-10 rounded-3 me-3">
                        <Shield className="text-danger" size={28} />
                    </div>
                    <div>
                        <h2 className="mb-0 fw-bold">Admin Dashboard</h2>
                        <p className="text-muted mb-0">Manage system-wide configurations, market calendars, and the stock universe.</p>
                    </div>
                </div>

                <Card className="border-0 shadow-sm rounded-4 overflow-hidden">
                    <Card.Body className="p-0">
                        <Tabs defaultActiveKey="config" id="admin-tabs" className="admin-tabs px-3 pt-3 border-bottom">
                            <Tab eventKey="config" title={<div className="d-flex align-items-center gap-2 py-2"><Settings size={18} /> System Config</div>}>
                                <div className="p-4">
                                    <ConfigTab />
                                </div>
                            </Tab>
                            <Tab eventKey="holidays" title={<div className="d-flex align-items-center gap-2 py-2"><Calendar size={18} /> Market Holidays</div>}>
                                <div className="p-4">
                                    <HolidaysTab />
                                </div>
                            </Tab>
                            <Tab eventKey="stocks" title={<div className="d-flex align-items-center gap-2 py-2"><Database size={18} /> Stock Universe</div>}>
                                <div className="p-4">
                                    <StockUniverseTab />
                                </div>
                            </Tab>
                        </Tabs>
                    </Card.Body>
                </Card>
            </Container>
        </>
    );
}

function ConfigTab() {
    const [configs, setConfigs] = useState<SystemConfig[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    const fetchData = async () => {
        try {
            const data = await getConfigs();
            setConfigs(data);
        } catch (err) {
            setError("Failed to load configurations.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchData(); }, []);

    const handleUpdate = async (key: string, value: string) => {
        try {
            await updateConfig(key, value);
            setSuccess(`Updated ${key} successfully.`);
            fetchData();
        } catch (err) {
            setError(`Failed to update ${key}.`);
        }
    };

    const handleReload = async () => {
        try {
            await reloadConfigCache();
            setSuccess("Configuration cache reloaded.");
        } catch (err) {
            setError("Failed to reload cache.");
        }
    };

    if (loading) return <Spinner animation="border" size="sm" />;

    return (
        <div>
           <div className="d-flex justify-content-between align-items-center mb-4">
                <h5 className="fw-bold mb-0">Global Runtime Settings</h5>
                <Button variant="outline-primary" size="sm" onClick={handleReload} className="d-flex align-items-center gap-2">
                    <RefreshCw size={14} /> Reload Cache
                </Button>
            </div>

            {error && <Alert variant="danger" dismissible onClose={() => setError(null)}>{error}</Alert>}
            {success && <Alert variant="success" dismissible onClose={() => setSuccess(null)}>{success}</Alert>}

            <Table responsive borderless className="align-middle">
                <thead>
                    <tr className="border-bottom text-muted small text-uppercase">
                        <th className="py-3 px-3">Key / Property</th>
                        <th className="py-3 px-3">Value</th>
                        <th className="py-3 px-3">Description</th>
                        <th className="py-3 px-3 text-end">Action</th>
                    </tr>
                </thead>
                <tbody>
                    {configs.map((cfg) => (
                        <tr key={cfg.key} className="border-bottom">
                            <td className="py-3 px-3">
                                <code className="text-primary fw-bold">{cfg.key}</code>
                                <div className="text-muted extra-small mt-1">Type: {cfg.value_type}</div>
                            </td>
                            <td className="py-3 px-3">
                                <Form.Control 
                                    size="sm" 
                                    defaultValue={cfg.value} 
                                    onBlur={(e) => {
                                        if (e.target.value !== cfg.value) {
                                            handleUpdate(cfg.key, e.target.value);
                                        }
                                    }}
                                />
                            </td>
                            <td className="py-3 px-3 small text-muted">{cfg.description}</td>
                            <td className="py-3 px-3 text-end">
                                <Badge bg="light" text="dark" className="fw-normal border">
                                    {cfg.updated_by || 'system'}
                                </Badge>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </Table>
        </div>
    );
}

function HolidaysTab() {
    const [holidays, setHolidays] = useState<MarketHoliday[]>([]);
    const [loading, setLoading] = useState(true);
    const [newDate, setNewDate] = useState("");
    const [newDesc, setNewDesc] = useState("");

    const fetchData = async () => {
        try {
            const data = await getHolidays(new Date().getFullYear());
            setHolidays(data.sort((a, b) => a.date.localeCompare(b.date)));
        } catch (err) { console.error(err); }
        finally { setLoading(false); }
    };

    useEffect(() => { fetchData(); }, []);

    const handleAdd = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await addHoliday(newDate, newDesc);
            setNewDate(""); setNewDesc("");
            fetchData();
        } catch (err) { alert("Failed to add holiday."); }
    };

    const handleDelete = async (date: string) => {
        if (!confirm(`Delete holiday for ${date}?`)) return;
        try {
            await deleteHoliday(date);
            fetchData();
        } catch (err) { alert("Failed to delete."); }
    };

    if (loading) return <Spinner animation="border" size="sm" />;

    return (
        <div>
            <h5 className="fw-bold mb-4">NSE Market Holidays</h5>
            
            <Form onSubmit={handleAdd} className="bg-light p-3 rounded-3 mb-4">
                <Row className="g-3 align-items-end">
                    <Col md={4}>
                        <Form.Label className="small fw-bold">Date</Form.Label>
                        <Form.Control type="date" value={newDate} onChange={(e) => setNewDate(e.target.value)} required />
                    </Col>
                    <Col md={6}>
                        <Form.Label className="small fw-bold">Description</Form.Label>
                        <Form.Control type="text" placeholder="e.g. Independence Day" value={newDesc} onChange={(e) => setNewDesc(e.target.value)} required />
                    </Col>
                    <Col md={2}>
                        <Button variant="primary" type="submit" className="w-100 d-flex align-items-center justify-content-center gap-2">
                            <Plus size={16} /> Add
                        </Button>
                    </Col>
                </Row>
            </Form>

            <Table responsive borderless hover>
                <thead>
                    <tr className="border-bottom text-muted small text-uppercase">
                        <th className="py-3 px-3">Date</th>
                        <th className="py-3 px-3">Holiday Name</th>
                        <th className="py-3 px-3 text-end">Action</th>
                    </tr>
                </thead>
                <tbody>
                    {holidays.map((h) => (
                        <tr key={h.date} className="border-bottom align-middle">
                            <td className="py-2 px-3 fw-semibold">{h.date}</td>
                            <td className="py-2 px-3">{h.description}</td>
                            <td className="py-2 px-3 text-end">
                                <Button variant="link" className="text-danger p-0" onClick={() => handleDelete(h.date)}>
                                    <Trash2 size={16} />
                                </Button>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </Table>
        </div>
    );
}

function StockUniverseTab() {
    const [stocks, setStocks] = useState<StockUniverseItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState("");
    const [page, setPage] = useState(0);
    const [total, setTotal] = useState(0);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const fetchData = async () => {
        setLoading(true);
        try {
            const data = await getStockUniverse({ skip: page * 50, limit: 50 });
            setStocks(data.stocks);
            setTotal(data.total);
        } catch (err) { console.error(err); }
        finally { setLoading(false); }
    };

    useEffect(() => { fetchData(); }, [page]);

    const handleToggle = async (stock: StockUniverseItem) => {
        try {
            await updateStockInUniverse(stock.symbol, { is_active: !stock.is_active });
            fetchData();
        } catch (err) { alert("Failed to update."); }
    };

    const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        if (!confirm("Import stocks from CSV? This will upsert matching symbols.")) return;

        try {
            await importStocksCSV(file);
            alert("Import successful.");
            fetchData();
        } catch (err) { alert("Import failed."); }
    };

    const handleReloadCache = async () => {
        try {
            await reloadStockUniverseCache();
            alert("Stock cache reloaded.");
        } catch (err) { console.error(err); }
    };

    const filteredStocks = stocks.filter(s => 
        s.symbol.toLowerCase().includes(searchTerm.toLowerCase()) || 
        s.name.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <div>
            <div className="d-flex justify-content-between align-items-center mb-4 gap-3">
                <div className="position-relative flex-grow-1" style={{ maxWidth: '400px' }}>
                    <Search className="position-absolute top-50 start-0 translate-middle-y ms-3 text-muted" size={18} />
                    <Form.Control 
                        type="text" 
                        placeholder="Filter current view..." 
                        className="ps-5 rounded-pill" 
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                </div>
                <div className="d-flex gap-2">
                    <input type="file" ref={fileInputRef} onChange={handleImport} style={{ display: 'none' }} accept=".csv" />
                    <Button variant="outline-primary" size="sm" onClick={() => fileInputRef.current?.click()} className="d-flex align-items-center gap-2">
                        <Upload size={14} /> Import CSV
                    </Button>
                    <Button variant="outline-secondary" size="sm" onClick={handleReloadCache} className="d-flex align-items-center gap-2">
                        <RefreshCw size={14} /> Refresh Cache
                    </Button>
                </div>
            </div>

            <Table responsive borderless hover className="align-middle">
                <thead>
                    <tr className="border-bottom text-muted small text-uppercase">
                        <th className="py-3 px-3">Symbol</th>
                        <th className="py-3 px-3">Company Name</th>
                        <th className="py-3 px-3">Sector</th>
                        <th className="py-3 px-3 text-center">Active</th>
                    </tr>
                </thead>
                <tbody>
                    {loading ? (
                        <tr><td colSpan={4} className="text-center py-5"><Spinner animation="border" size="sm" /></td></tr>
                    ) : filteredStocks.map((s) => (
                        <tr key={s.symbol} className="border-bottom">
                            <td className="py-2 px-3 fw-bold">{s.symbol}</td>
                            <td className="py-2 px-3 small">{s.name}</td>
                            <td className="py-2 px-3 small">{s.sector}</td>
                            <td className="py-2 px-3 text-center">
                                <Button variant="link" className="p-0" onClick={() => handleToggle(s)}>
                                    {s.is_active ? <CheckCircle className="text-success" size={20} /> : <XCircle className="text-muted" size={20} />}
                                </Button>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </Table>

            <div className="d-flex justify-content-between align-items-center mt-3">
                <span className="small text-muted">Showing {stocks.length} of {total} stocks</span>
                <div className="d-flex gap-2">
                    <Button size="sm" variant="outline-secondary" disabled={page === 0} onClick={() => setPage(p => p - 1)}>Prev</Button>
                    <Button size="sm" variant="outline-secondary" disabled={(page + 1) * 50 >= total} onClick={() => setPage(p => p + 1)}>Next</Button>
                </div>
            </div>
        </div>
    );
}
