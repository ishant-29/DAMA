import { useEffect, useState } from "react";
import { getMarketRegime } from "../services/api";

interface RegimeData {
  regime: string;
  india_vix: number;
  description: string;
  allow_buy_signals: boolean;
  min_confidence: number;
  nifty_return_20d: number;
}

const REGIME_STYLES: Record<string, { bg: string; border: string; text: string; dot: string }> = {
  BULL:             { bg: "rgba(34,197,94,0.10)",  border: "1px solid rgba(34,197,94,0.4)",  text: "text-success",  dot: "bg-success" },
  RESISTANCE:       { bg: "rgba(234,179,8,0.10)",  border: "1px solid rgba(234,179,8,0.4)",  text: "text-warning",  dot: "bg-warning" },
  NEUTRAL:          { bg: "rgba(156,163,175,0.10)", border: "1px solid rgba(156,163,175,0.4)", text: "text-secondary", dot: "bg-secondary" },
  BEAR:             { bg: "rgba(239,68,68,0.10)",  border: "1px solid rgba(239,68,68,0.4)",  text: "text-danger",   dot: "bg-danger" },
  HIGH_VOLATILITY:  { bg: "rgba(239,68,68,0.20)",  border: "1px solid rgba(239,68,68,0.6)",  text: "text-danger",   dot: "bg-danger" },
};

export const RegimeBanner = () => {
  const [regime, setRegime] = useState<RegimeData | null>(null);

  useEffect(() => {
    getMarketRegime().then(setRegime).catch(console.error);
  }, []);

  if (!regime) return null;

  const style = REGIME_STYLES[regime.regime] ?? REGIME_STYLES.NEUTRAL;

  return (
    <div
      className={`px-4 py-3 rounded-3 mb-4 ${style.text}`}
      style={{ background: style.bg, border: style.border, fontSize: '0.875rem' }}
    >
      <div className="d-flex align-items-center gap-3 mb-1">
        <span className={`rounded-circle ${style.dot}`} style={{ width: 8, height: 8, display: 'inline-block' }} />
        <span className="fw-semibold">{regime.description}</span>
        <div className="ms-auto d-flex gap-3 opacity-75" style={{ fontSize: '0.75rem' }}>
          <span>VIX: <strong>{regime.india_vix?.toFixed(1)}</strong></span>
          <span>Nifty 20D: <strong>{regime.nifty_return_20d?.toFixed(1)}%</strong></span>
        </div>
      </div>
      <div className="ps-4 small opacity-75 fw-bold">
        {regime.regime === 'HIGH_VOLATILITY' && "ALL signals halted, no signal suggestion due to severe market volatility"}
        {regime.regime === 'BEAR' && "NIFTY 50 is trading below 10 EMA, 20 EMA, and 50 EMA indicating strong bearish momentum."}
        {regime.regime === 'RESISTANCE' && "Short-term momentum is positive, but the market still faces resistance near the 50 EMA."}
        {regime.regime === 'NEUTRAL' && "Neutral Conditions: Mixed momentum, proceeding with caution."}
        {regime.regime === 'BULL' && "NIFTY 50 is trading above all major moving averages indicating strong bullish momentum."}
      </div>
    </div>
  );
};

export default RegimeBanner;
