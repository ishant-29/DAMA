import { useEffect, useState } from 'react';

interface CountUpProps {
    end: number;
    duration?: number;
    prefix?: string;
    suffix?: string;
    decimals?: number;
    className?: string;
    separator?: string;
}

export default function CountUp({ end, duration = 2000, prefix = '', suffix = '', decimals = 0, className = '', separator }: CountUpProps) {
    const [count, setCount] = useState(0);

    useEffect(() => {
        let startTime: number;
        let animationFrame: number;

        const animate = (timestamp: number) => {
            if (!startTime) startTime = timestamp;
            const progress = timestamp - startTime;
            const percentage = Math.min(progress / duration, 1);

            // Ease out quart
            const ease = 1 - Math.pow(1 - percentage, 4);

            setCount(end * ease);

            if (progress < duration) {
                animationFrame = requestAnimationFrame(animate);
            } else {
                setCount(end); // Ensure exact end value
            }
        };

        animationFrame = requestAnimationFrame(animate);

        return () => cancelAnimationFrame(animationFrame);
    }, [end, duration]);

    const formattedCount = separator
        ? count.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
        : count.toFixed(decimals);

    return (
        <span className={className}>
            {prefix}{formattedCount}{suffix}
        </span>
    );
}
