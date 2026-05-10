
import { Container } from 'react-bootstrap';
import { APP_CONFIG } from '../config';

export default function Footer() {
    return (
        <footer className="app-footer py-3 mt-auto border-top border-secondary">
            <Container className="d-flex flex-column flex-md-row justify-content-between align-items-center">
                <div className="text-secondary small mb-2 mb-md-0">
                    <span className="fw-bold text-accent">{APP_CONFIG.appName}</span>
                    <span className="mx-2 opacity-25">|</span>
                    <span className="text-muted">{APP_CONFIG.appSubtitle}</span>
                </div>

                <div className="d-flex gap-4 align-items-center">
                    <div className="d-flex align-items-center gap-2 small">
                        <span className="position-relative d-flex h-2 w-2">
                            <span className="animate-ping position-absolute d-inline-flex h-100 w-100 rounded-circle bg-success opacity-75"></span>
                            <span className="d-inline-flex rounded-circle height-8 width-8 bg-success" style={{ width: '8px', height: '8px' }}></span>
                        </span>
                        <span className="text-success fw-bold" style={{ fontSize: '0.75rem', letterSpacing: '1px' }}>SYSTEM ONLINE</span>
                    </div>
                </div>
            </Container>
            <style>{`
                .animate-ping {
                    animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;
                }
                @keyframes ping {
                    75%, 100% { transform: scale(2); opacity: 0; }
                }
            `}</style>
        </footer>
    );
}
