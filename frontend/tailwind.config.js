/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            fontFamily: {
                sans: ['Outfit', 'sans-serif'],
                mono: ['Space Grotesk', 'monospace'],
            },
            colors: {
                bg: {
                    DEFAULT: '#f8fafc', // Slate 50 - Very soft gray/white
                    card: '#ffffff',    // Pure White
                    lighter: '#f1f5f9', // Slate 100
                },
                primary: {
                    DEFAULT: '#10b981', // Emerald 500 (Growth/Money)
                    hover: '#059669',   // Emerald 600
                    glow: 'rgba(16, 185, 129, 0.4)',
                },
                accent: {
                    DEFAULT: '#8b5cf6', // Violet 500 (Premium)
                    hover: '#7c3aed',   // Violet 600
                    glow: 'rgba(139, 92, 246, 0.4)',
                },
                text: {
                    primary: '#1e293b',  // Slate 800 - High contrast
                    secondary: '#64748b', // Slate 500
                    muted: '#94a3b8',    // Slate 400
                }
            },
            boxShadow: {
                'glow': '0 0 15px -3px var(--tw-shadow-color)',
                'glass': '0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)',
                'card': '0 10px 15px -3px rgba(0, 0, 0, 0.03), 0 4px 6px -2px rgba(0, 0, 0, 0.02)',
            },
            backgroundImage: {
                'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
                'hero-glow': 'linear-gradient(135deg, #f0fdf4 0%, #ffffff 100%)', // Very subtle emerald tint
            }
        },
    },
    plugins: [],
}
