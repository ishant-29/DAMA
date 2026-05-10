import { Navbar, Nav, Container, NavDropdown } from 'react-bootstrap';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { getHealthStatus, getCurrentUser, type UserProfile, clearAuthToken, getAuthToken } from '../services/api';
import { APP_CONFIG } from '../config';
import { Settings, Shield, LogOut } from 'lucide-react';

export default function AppNavbar() {
    const location = useLocation();
    const navigate = useNavigate();
    const [isHealthy, setIsHealthy] = useState(true);
    const [user, setUser] = useState<UserProfile | null>(null);

    useEffect(() => {
        const checkHealth = () => {
            getHealthStatus().then(setIsHealthy).catch(() => setIsHealthy(false));
        };
        
        const fetchUser = async () => {
            const token = getAuthToken();
            if (token) {
                try {
                    const profile = await getCurrentUser();
                    setUser(profile);
                } catch (err) {
                    console.error("Failed to fetch user in navbar", err);
                }
            }
        };
        
        checkHealth();
        fetchUser();
        
        const interval = setInterval(checkHealth, APP_CONFIG.healthPollIntervalMs);
        return () => clearInterval(interval);
    }, []);

    const handleLogout = () => {
        clearAuthToken();
        navigate('/login');
    };

    return (
        <Navbar expand="lg" className="navbar-custom sticky-top py-3 border-0 mb-4"
            style={{
                background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.05), rgba(59, 130, 246, 0.05))',
                backdropFilter: 'blur(20px)',
                borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
                boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)'
            }}>
            <Container fluid>
                <Navbar.Brand as={Link} to="/" className="brand-logo d-flex align-items-center gap-3">
                    <div className="rounded-3 d-flex align-items-center justify-content-center position-relative"
                        style={{
                            width: '48px',
                            height: '48px',
                            background: 'linear-gradient(135deg, #10b981, #3b82f6)',
                            boxShadow: '0 8px 24px rgba(16, 185, 129, 0.4)'
                        }}>
                        <span className="text-white fw-bold" style={{ fontSize: '1.5rem' }}>⚡</span>
                    </div>
                    <span className="brand-text fw-bold" style={{
                        fontSize: '1.75rem',
                        letterSpacing: '-1px',
                        background: 'linear-gradient(135deg, #10b981, #3b82f6)',
                        WebkitBackgroundClip: 'text',
                        WebkitTextFillColor: 'transparent',
                        backgroundClip: 'text'
                    }}>
                        DAMA
                    </span>
                </Navbar.Brand>

                <Navbar.Toggle aria-controls="basic-navbar-nav" className="border-0" />

                <Navbar.Collapse id="basic-navbar-nav">
                    <Nav className="ms-auto gap-2 align-items-center">
                        <Nav.Link as={Link} to="/" className={`nav-link-custom px-3 py-2 rounded-pill ${location.pathname === '/' ? 'active' : ''}`}>
                            📊 Signals
                        </Nav.Link>

                        <Nav.Link as={Link} to="/heatmap" className={`nav-link-custom px-3 py-2 rounded-pill ${location.pathname === '/heatmap' ? 'active' : ''}`}>
                            🔥 Heatmap
                        </Nav.Link>

                        <Nav.Link as={Link} to="/high-risk" className={`nav-link-custom px-3 py-2 rounded-pill ${location.pathname === '/high-risk' ? 'active' : ''}`}>
                            ⚠️ High Risk
                        </Nav.Link>

                        <Nav.Link as={Link} to="/performance" className={`nav-link-custom px-3 py-2 rounded-pill ${location.pathname === '/performance' ? 'active' : ''}`}>
                            📈 Performance
                        </Nav.Link>

                        <div className="vr d-none d-lg-block mx-2 opacity-25"></div>

                        {user && (
                            <NavDropdown
                                title={
                                    <div className="d-flex align-items-center gap-2" style={{ cursor: 'pointer' }}>
                                        {/* ── Premium Avatar ── */}
                                        <div style={{ position: 'relative', width: 38, height: 38, flexShrink: 0 }}>
                                            {/* Spinning gradient ring */}
                                            <div style={{
                                                position: 'absolute', inset: -2, borderRadius: '50%',
                                                background: 'conic-gradient(#10b981, #6366f1, #10b981)',
                                                animation: 'avatarRingSpin 4s linear infinite',
                                            }} />
                                            {/* White gap */}
                                            <div style={{
                                                position: 'absolute', inset: 1, borderRadius: '50%',
                                                background: '#fff',
                                            }} />
                                            {/* Face */}
                                            <div style={{
                                                position: 'absolute', inset: 3, borderRadius: '50%',
                                                background: 'linear-gradient(135deg, #10b981 0%, #6366f1 100%)',
                                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                                boxShadow: '0 2px 10px rgba(16,185,129,0.45)',
                                                zIndex: 1,
                                            }}>
                                                <span style={{
                                                    color: '#fff', fontWeight: 800, fontSize: '0.78rem',
                                                    textTransform: 'uppercase', letterSpacing: '-0.5px',
                                                }}>
                                                    {user.username.charAt(0)}
                                                </span>
                                            </div>
                                        </div>
                                        {/* Name + role */}
                                        <div className="d-none d-lg-flex flex-column" style={{ lineHeight: 1.25 }}>
                                            <span style={{ fontWeight: 700, fontSize: '0.83rem', color: '#0f172a', letterSpacing: '-0.3px' }}>
                                                {user.username}
                                            </span>
                                            <span style={{ fontSize: '0.6rem', fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase', color: '#10b981' }}>
                                                {user.is_admin ? '✦ Admin' : '◆ Trader'}
                                            </span>
                                        </div>
                                    </div>
                                }
                                id="user-dropdown"
                                align="end"
                                className="user-dropdown-custom"
                            >
                                {/* Dropdown header */}
                                <div style={{ padding: '14px 16px 10px', borderBottom: '1px solid #f1f5f9', marginBottom: 6 }}>
                                    <div className="d-flex align-items-center gap-3">
                                        <div style={{
                                            width: 44, height: 44, borderRadius: '50%', flexShrink: 0,
                                            background: 'linear-gradient(135deg, #10b981 0%, #6366f1 100%)',
                                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                                            boxShadow: '0 4px 14px rgba(16,185,129,0.35)',
                                            border: '2.5px solid #fff',
                                        }}>
                                            <span style={{ color: '#fff', fontWeight: 800, fontSize: '1.05rem', textTransform: 'uppercase' }}>
                                                {user.username.charAt(0)}
                                            </span>
                                        </div>
                                        <div>
                                            <div style={{ fontWeight: 700, color: '#0f172a', fontSize: '0.9rem' }}>{user.username}</div>
                                            <div style={{ fontSize: '0.71rem', color: '#64748b', marginTop: 1 }}>
                                                {user.is_admin ? '🛡️ Administrator' : '📊 Trader Account'}
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <NavDropdown.Item as={Link} to="/settings" className="d-flex align-items-center gap-2 py-2">
                                    <Settings size={15} /> Trading Settings
                                </NavDropdown.Item>

                                {user.is_admin && (
                                    <NavDropdown.Item as={Link} to="/admin" className="d-flex align-items-center gap-2 py-2 text-danger">
                                        <Shield size={15} /> Admin Dashboard
                                    </NavDropdown.Item>
                                )}

                                <NavDropdown.Divider />

                                <NavDropdown.Item onClick={handleLogout} className="d-flex align-items-center gap-2 py-2 text-danger">
                                    <LogOut size={15} /> Sign Out
                                </NavDropdown.Item>
                            </NavDropdown>
                        )}

                        {/* LIVE / OFFLINE pill */}
                        <div style={{
                            display: 'flex', alignItems: 'center', gap: 6,
                            padding: '5px 12px',
                            borderRadius: 20,
                            background: isHealthy ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
                            border: `1px solid ${isHealthy ? 'rgba(16,185,129,0.28)' : 'rgba(239,68,68,0.28)'}`,
                            transition: 'all 0.3s',
                        }}>
                            <div style={{
                                width: 7, height: 7, borderRadius: '50%',
                                background: isHealthy ? '#10b981' : '#ef4444',
                                boxShadow: isHealthy ? '0 0 7px #10b981' : '0 0 7px #ef4444',
                                animation: isHealthy ? 'livePulse 1.8s ease-in-out infinite' : 'none',
                                flexShrink: 0,
                            }} />
                            <span style={{
                                fontSize: '0.68rem', fontWeight: 700, letterSpacing: 1,
                                color: isHealthy ? '#10b981' : '#ef4444',
                            }}>
                                {isHealthy ? 'LIVE' : 'OFFLINE'}
                            </span>
                        </div>
                    </Nav>
                </Navbar.Collapse>
            </Container>

            <style>{`
                .nav-link-custom {
                    transition: all 0.2s;
                    color: #6b7280;
                    font-weight: 500;
                }
                .nav-link-custom:hover {
                    color: #10b981;
                    background: rgba(16, 185, 129, 0.05);
                }
                .nav-link-custom.active {
                    background: linear-gradient(135deg, #10b981, #059669) !important;
                    color: #fff !important;
                    font-weight: 700;
                    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
                }
                /* ── User dropdown ── */
                .user-dropdown-custom .dropdown-toggle::after { display: none; }
                .user-dropdown-custom .dropdown-menu {
                    border: none;
                    box-shadow: 0 16px 48px rgba(0,0,0,0.14);
                    border-radius: 16px;
                    padding: 6px;
                    margin-top: 12px;
                    min-width: 220px;
                    background: rgba(255,255,255,0.97);
                    backdrop-filter: blur(16px);
                }
                .user-dropdown-custom .dropdown-item {
                    border-radius: 10px;
                    font-size: 0.875rem;
                    color: #374151;
                    font-weight: 500;
                    padding: 9px 14px;
                    transition: background 0.15s;
                }
                .user-dropdown-custom .dropdown-item:hover {
                    background: linear-gradient(135deg, rgba(16,185,129,0.08), rgba(99,102,241,0.08));
                    color: #0f172a;
                }
                .user-dropdown-custom .dropdown-divider { margin: 4px 0; opacity: 0.15; }
                /* ── Animations ── */
                @keyframes avatarRingSpin {
                    from { transform: rotate(0deg); }
                    to   { transform: rotate(360deg); }
                }
                @keyframes livePulse {
                    0%, 100% { opacity: 1; transform: scale(1); }
                    50%       { opacity: 0.55; transform: scale(0.85); }
                }
            `}</style>
        </Navbar>
    );
}
