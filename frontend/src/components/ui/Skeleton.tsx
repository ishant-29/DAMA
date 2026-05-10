
interface SkeletonProps {
    width?: string | number;
    height?: string | number;
    className?: string;
    variant?: 'text' | 'circular' | 'rectangular';
}

export default function Skeleton({ width, height, className = '', variant = 'text' }: SkeletonProps) {
    const style = {
        width,
        height,
        borderRadius: variant === 'circular' ? '50%' : '8px',
    };

    return <div className={`skeleton ${className}`} style={style}></div>;
}
