
import React from 'react';
import type { LucideIcon } from 'lucide-react';

interface EmptyStateProps {
    icon: LucideIcon;
    title: string;
    description: string;
    action?: React.ReactNode;
}

export default function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
    return (
        <div className="text-center py-5 animate-fade-in">
            <div className="d-inline-flex align-items-center justify-content-center p-4 rounded-circle bg-light mb-4 shadow-sm animate-float">
                <Icon size={48} className="text-secondary opacity-50" />
            </div>
            <h4 className="fw-bold text-primary mb-2">{title}</h4>
            <p className="text-secondary mw-md mx-auto mb-4" style={{ maxWidth: '400px' }}>{description}</p>
            {action}
        </div>
    );
}
