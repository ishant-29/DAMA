import { useState, useEffect } from 'react';
import { Container, Row, Col, Card, Form, Button, Alert, Spinner } from 'react-bootstrap';
import AppNavbar from '../components/Navbar';
import { getUserSettings, updateUserSettings, resetUserSettings, type UserSettings } from '../services/api';
import { Settings, Save, RotateCcw, AlertTriangle } from 'lucide-react';

export default function SettingsPage() {
    const [settings, setSettings] = useState<UserSettings | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    useEffect(() => {
        const fetchSettings = async () => {
            try {
                const data = await getUserSettings();
                setSettings(data);
            } catch (err) {
                setError("Failed to load settings. Please try again.");
            } finally {
                setLoading(false);
            }
        };
        fetchSettings();
    }, []);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!settings) return;
        const { name, value, type } = e.target;
        setSettings({
            ...settings,
            [name]: type === 'number' ? parseFloat(value) : value
        });
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!settings) return;

        setSaving(true);
        setError(null);
        setSuccess(null);

        try {
            await updateUserSettings(settings);
            setSuccess("Settings updated successfully!");
        } catch (err: any) {
            setError(err.response?.data?.detail || "Failed to update settings. Check for range errors.");
        } finally {
            setSaving(false);
        }
    };

    const handleReset = async () => {
        if (!confirm("Are you sure you want to reset all settings to system defaults?")) return;

        setSaving(true);
        try {
            const data = await resetUserSettings();
            setSettings(data);
            setSuccess("Settings reset to defaults.");
        } catch (err) {
            setError("Failed to reset settings.");
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="min-vh-100 d-flex align-items-center justify-content-center">
                <Spinner animation="border" variant="primary" />
            </div>
        );
    }

    return (
        <>
            <AppNavbar />
            <Container className="py-5">
                <Row className="justify-content-center">
                    <Col md={8} lg={6}>
                        <div className="d-flex align-items-center mb-4">
                            <div className="p-2 bg-primary bg-opacity-10 rounded-3 me-3">
                                <Settings className="text-primary" size={28} />
                            </div>
                            <h2 className="mb-0 fw-bold">Trading Settings</h2>
                        </div>

                        {error && <Alert variant="danger">{error}</Alert>}
                        {success && <Alert variant="success">{success}</Alert>}

                        <Card className="border-0 shadow-sm overflow-hidden rounded-4 mb-4">
                            <Card.Header className="bg-white border-bottom py-3">
                                <h5 className="mb-0 fw-bold">Risk Management</h5>
                                <p className="text-muted small mb-0">Customize your auto-calculated position sizes and stop-loss levels.</p>
                            </Card.Header>
                            <Card.Body className="p-4">
                                <Form onSubmit={handleSubmit}>
                                    <Row className="g-4">
                                        <Col md={6}>
                                            <Form.Group controlId="minConfidence">
                                                <Form.Label className="small fw-semibold text-muted text-uppercase mb-2">Min Confidence Threshold</Form.Label>
                                                <Form.Control
                                                    type="number"
                                                    step="0.01"
                                                    name="min_confidence"
                                                    value={settings?.min_confidence}
                                                    onChange={handleChange}
                                                    required
                                                />
                                            </Form.Group>
                                        </Col>
                                        <Col md={6}>
                                            <Form.Group controlId="kellyFraction">
                                                <Form.Label className="small fw-semibold text-muted text-uppercase mb-2">Kelly Fraction (Safe: 0.5)</Form.Label>
                                                <Form.Control
                                                    type="number"
                                                    step="0.01"
                                                    name="kelly_fraction"
                                                    value={settings?.kelly_fraction}
                                                    onChange={handleChange}
                                                    required
                                                />
                                            </Form.Group>
                                        </Col>
                                    </Row>

                                    <div className="d-flex gap-3 mt-5">
                                        <Button
                                            variant="primary"
                                            type="submit"
                                            disabled={saving}
                                            className="px-4 py-2 rounded-3 d-flex align-items-center gap-2"
                                        >
                                            <Save size={18} />
                                            {saving ? 'Saving...' : 'Save Changes'}
                                        </Button>
                                        <Button
                                            variant="outline-secondary"
                                            type="button"
                                            onClick={handleReset}
                                            disabled={saving}
                                            className="px-4 py-2 rounded-3 d-flex align-items-center gap-2"
                                        >
                                            <RotateCcw size={18} />
                                            Reset Defaults
                                        </Button>
                                    </div>
                                </Form>
                            </Card.Body>
                        </Card>

                        <Alert variant="warning" className="border-0 shadow-sm rounded-4 d-flex gap-3">
                            <AlertTriangle className="flex-shrink-0" size={24} />
                                <div>
                                    <h6 className="fw-bold mb-1">Impact Check</h6>
                                    <p className="mb-0 small">Updating these settings will change how future signals are evaluated and how the position sizer allocates your paper trading capital. Existing trades will not be affected.</p>
                                </div>
                        </Alert>
                    </Col>
                </Row>
            </Container>
        </>
    );
}
