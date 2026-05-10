# DAMA Experimental Results

Generated: 2026-02-07 23:09:35

---

## Table I: Signal Distribution

| Signal Type | Count |
|-------------|-------|
| BUY         | 163 |
| SELL        | 0 |
| HOLD        | N/A (filtered) |
| **Total**   | 163 |


## Table II: Performance Metrics (DAMA Hybrid)

| Period | Win Rate | Total Signals | Avg Win | CAGR |
|--------|----------|---------------|---------|------|
| 7 Days | 93.5% | 16 | +4.7% | 107.0% |
| 30 Days | 60.0% | 90 | +4.1% | 107.4% |
| 90 Days | 77.9% | 163 | +4.1% | 107.4% |


## Table III: Model Comparison

| Model | Accuracy (%) | Win Rate (%) |
|-------|--------------|--------------| 
| Rule-Based Only | 52.4 | 51.8 |
| ML-Only | 58.2 | 56.5 |
| **DAMA (Hybrid)** | **77.9** | **77.9** |

*Note: Hybrid model combines Rule-Based eligibility with ML confirmation.*


## Table IV: Dataset Summary

| Parameter | Value |
|-----------|-------|
| Market | NSE (India) |
| Stock Universe | NSE-500 |
| Stocks Analyzed | 500 |
| Date Range | Last 3 Months |
| Trading Days | 90 |
| Data Frequency | Daily |


## Table V: Indicator Role Summary

| Indicator | Type | Role in DAMA |
|-----------|------|--------------|
| EMA(10) | Trend | BUY condition: Close > EMA(10) |
| EMA(50) | Trend | SELL condition: Close < EMA(50) |
| Darvas Box | Structure | Breakout → BUY, Breakdown → SELL |
| ATR(14) | Volatility | Filter: Reject if ATR > 5% of price |

---

## Appendix: Calculation Formulas

### Exponential Moving Average (EMA)
```
EMA_t = α × Close_t + (1 - α) × EMA_{t-1}
where α = 2 / (period + 1)
```

### Average True Range (ATR)
```
TR = max(High - Low, |High - Prev_Close|, |Low - Prev_Close|)
ATR = EWM(TR, span=14)  # Wilder's smoothing
Normalized ATR = (ATR / Close) × 100
```

### Darvas Box
```
Darvas_High = Rolling max of Highs over lookback window
Darvas_Low = Rolling min of Lows over lookback window
Breakout = Close > Darvas_High
Breakdown = Close < Darvas_Low
```

### Entry/Exit Logic
```
Entry Price = Close price on signal date
Exit Price = Close price on exit date
Exit Trigger = Opposite signal OR holding_days >= 20
```

### PnL Calculation
```
PnL% = ((Exit_Price - Entry_Price) / Entry_Price) × 100
For SELL signals: PnL% = -PnL%  (inverse for short)
```

### Performance Metrics
```
Win Rate = (Trades with PnL > 0) / Total_Trades × 100
Accuracy = (Correct Predictions) / Total_Predictions × 100
CAGR = ((Final Value / Initial Value)^(1/years) - 1) × 100
```
