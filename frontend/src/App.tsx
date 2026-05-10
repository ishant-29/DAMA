import { BrowserRouter as Router, Routes, Route, Link, Navigate } from 'react-router-dom';
import { Component, type ReactNode, useState, useEffect } from 'react';
import Dashboard from './pages/Dashboard';
import StockPage from './pages/StockPage';
import Heatmap from './pages/Heatmap';
import HighRiskPage from './pages/HighRiskPage';
import PerformanceDashboard from './pages/PerformanceDashboard';
import SettingsPage from './pages/SettingsPage';
import AdminPage from './pages/AdminPage';
import LoginPage from './pages/LoginPage';
import { getAuthToken, getCurrentUser, type UserProfile } from './services/api';

import Footer from './components/Footer';

// ── Error Boundary ──────────────────────────────────
interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    if (import.meta.env.DEV) console.error('ErrorBoundary caught:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="d-flex flex-column align-items-center justify-content-center min-vh-100 text-center p-4">
          <h1 className="text-danger mb-3">Something went wrong</h1>
          <p className="text-muted mb-4">{this.state.error?.message}</p>
          <button
            className="btn btn-outline-primary"
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.href = '/';
            }}
          >
            Return to Dashboard
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Auth Context / Props ───────────────────────────
interface AuthProps {
  user: UserProfile | null;
  loading: boolean;
}

// ── Private Route Guards ─────────────────────────────
function PrivateRoute({ children }: { children: ReactNode }) {
  const token = getAuthToken();
  return token ? <>{children}</> : <Navigate to="/login" replace />;
}

function AdminPrivateRoute({ children, user, loading }: { children: ReactNode } & AuthProps) {
  const token = getAuthToken();
  if (!token) return <Navigate to="/login" replace />;
  if (loading) return null;
  if (user?.is_admin) return <>{children}</>;
  return <Navigate to="/" replace />;
}

// ── 404 Page ────────────────────────────────────────
function NotFoundPage() {
  return (
    <div className="d-flex flex-column align-items-center justify-content-center" style={{ minHeight: '60vh' }}>
      <h1 className="display-1 text-muted">404</h1>
      <p className="lead text-muted mb-4">Page not found</p>
      <Link to="/" className="btn btn-outline-primary">Back to Dashboard</Link>
    </div>
  );
}

// ── App ─────────────────────────────────────────────
function App() {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchUser = async () => {
      const token = getAuthToken();
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const profile = await getCurrentUser();
        setUser(profile);
      } catch (err) {
        console.error("Failed to fetch user profile", err);
      } finally {
        setLoading(false);
      }
    };
    fetchUser();
  }, []);

  return (
    <ErrorBoundary>
      <Router>
        <div className="d-flex flex-column min-vh-100 position-relative overflow-hidden">
          {/* Background FX */}
          <div className="bg-blob blob-1"></div>
          <div className="bg-blob blob-2"></div>
          <div className="bg-blob blob-3"></div>

          <div className="flex-grow-1" style={{ zIndex: 1 }}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />

              <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
              <Route path="/heatmap" element={<PrivateRoute><Heatmap /></PrivateRoute>} />
              <Route path="/high-risk" element={<PrivateRoute><HighRiskPage /></PrivateRoute>} />
              <Route path="/performance" element={<PrivateRoute><PerformanceDashboard /></PrivateRoute>} />
              <Route path="/stock/:symbol" element={<PrivateRoute><StockPage /></PrivateRoute>} />
              
              {/* Added Routes */}
              <Route path="/settings" element={<PrivateRoute><SettingsPage /></PrivateRoute>} />
              <Route 
                path="/admin" 
                element={
                  <AdminPrivateRoute user={user} loading={loading}>
                    <AdminPage />
                  </AdminPrivateRoute>
                } 
              />

              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </div>
          <Footer />
        </div>
      </Router>
    </ErrorBoundary>
  );
}

export default App;
