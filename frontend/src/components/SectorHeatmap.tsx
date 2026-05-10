import { useEffect, useState } from 'react';


interface Sector {
    sector: string;
    score: number;
    change_7d: number;
}

const SectorHeatmap: React.FC = () => {
    const [sectors, setSectors] = useState<Sector[]>([]);

    useEffect(() => {
        // In real app: api.get('/sector/sentiment')
        // Stub for now if backend not fully wired with data
        const fetchSectors = async () => {
            try {
                // const res = await api.get('/sector/sentiment');
                // setSectors(res.data);

                // Mock for immediate display since we just added the route
                setSectors([
                    { "sector": "BANKING", "score": 0.15, "change_7d": 2.5 },
                    { "sector": "IT", "score": -0.05, "change_7d": -1.2 },
                    { "sector": "ENERGY", "score": 0.08, "change_7d": 1.1 },
                    { "sector": "PHARMA", "score": 0.02, "change_7d": 0.4 },
                    { "sector": "AUTO", "score": 0.12, "change_7d": 3.0 }
                ])
            } catch (e) {
                console.error(e);
            }
        };
        fetchSectors();
    }, []);

    return (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
            {sectors.map((s) => (
                <div
                    key={s.sector}
                    className={`p-4 rounded-xl shadow-sm border ${s.score > 0.1 ? 'bg-green-100 border-green-200' :
                        s.score < -0.1 ? 'bg-red-100 border-red-200' : 'bg-white border-gray-100'
                        }`}
                >
                    <div className="text-xs font-bold text-gray-500 uppercase">{s.sector}</div>
                    <div className="flex items-end justify-between mt-1">
                        <span className={`text-lg font-bold ${s.score > 0 ? 'text-green-700' : 'text-red-700'}`}>
                            {s.score > 0 ? '+' : ''}{(s.score * 100).toFixed(0)}%
                        </span>
                        <span className="text-xs text-gray-400">{s.change_7d}% 7d</span>
                    </div>
                </div>
            ))}
        </div>
    );
};

export default SectorHeatmap;
