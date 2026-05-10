import { useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Container, Card, Form, Button, Alert } from 'react-bootstrap';
import { login, register } from '../services/api';

/**
 * Login page — FIXED: S10-01 / S3-02
 * Replaces the old hardcoded admin/admin auto-login with a proper login form.
 */
export default function LoginPage() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [isRegistering, setIsRegistering] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();

    const reason = searchParams.get('reason');

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            if (isRegistering) {
                const result = await register(username, password);
                if (result.success) {
                    navigate('/', { replace: true });
                } else {
                    setError(result.message || 'Registration failed.');
                }
            } else {
                const success = await login(username, password);
                if (success) {
                    navigate('/', { replace: true });
                } else {
                    setError('Invalid username or password.');
                }
            }
        } catch {
            setError('Connection error. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-vh-100 d-flex align-items-center justify-content-center" style={{ background: 'var(--bg-dark, #0f1117)' }}>
            <Container style={{ maxWidth: 420 }}>
                <Card className="glass-card border-0 shadow-lg">
                    <Card.Body className="p-5">
                        <h2 className="text-center fw-bold text-primary mb-2">NSE Signal Engine</h2>
                        <p className="text-center text-muted mb-4">
                            {isRegistering ? 'Create your account' : 'Sign in to continue'}
                        </p>

                        {reason === 'session_expired' && (
                            <Alert variant="warning" className="py-2 small">
                                Your session has expired. Please log in again.
                            </Alert>
                        )}

                        {error && <Alert variant="danger" className="py-2 small">{error}</Alert>}

                        <Form onSubmit={handleSubmit}>
                            <Form.Group className="mb-3">
                                <Form.Label className="text-secondary small">Username</Form.Label>
                                <Form.Control
                                    id="login-username"
                                    type="text"
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    placeholder="Enter username"
                                    required
                                    autoFocus
                                />
                            </Form.Group>

                            <Form.Group className="mb-4">
                                <Form.Label className="text-secondary small">Password</Form.Label>
                                <Form.Control
                                    id="login-password"
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="Enter password"
                                    required
                                />
                            </Form.Group>

                            <Button
                                id="login-submit"
                                type="submit"
                                variant="primary"
                                className="w-100 py-2 fw-semibold"
                                disabled={loading}
                            >
                                {loading ? 'Please wait...' : isRegistering ? 'Create Account' : 'Sign In'}
                            </Button>
                        </Form>

                        <div className="text-center mt-3">
                            <button
                                className="btn btn-link text-muted small p-0"
                                onClick={() => { setIsRegistering(!isRegistering); setError(''); }}
                            >
                                {isRegistering ? 'Already have an account? Sign in' : 'Need an account? Register'}
                            </button>
                        </div>
                    </Card.Body>
                </Card>
            </Container>
        </div>
    );
}
