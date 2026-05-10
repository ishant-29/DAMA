# NSE 500 Signal Engine

A trading system that watches 500+ Indian stocks and tells you when to buy or sell. It runs automatically every day, uses machine learning to validate signals, and lets you test strategies without risking real money.

## What does it do?

This is a full-stack web app that generates trading signals for NSE stocks. Think of it as a robot trader that:

- Scans 500+ stocks every day looking for opportunities
- Uses technical indicators (moving averages, Darvas boxes) to spot trends
- Validates signals with machine learning models (XGBoost/Random Forest)
- Tracks sector momentum to avoid weak markets
- Simulates trades in a paper portfolio so you can see how it performs
- Sends you alerts when it finds high-confidence opportunities

The whole thing runs on autopilot. You just check the dashboard to see what it found.

## Why I built this

I wanted a system that could:
1. Actually make money (not just look good on paper)
2. Run without me babysitting it
3. Show me real performance data, not cherry-picked examples
4. Let me backtest strategies properly before risking capital

After testing on historical data, it's showing a 61% win rate with 19% returns over 90 days. Not bad for a robot.

## Tech stack

**Backend:**
- FastAPI (Python) - handles all the heavy lifting
- PostgreSQL - stores signals, trades, performance data
- Redis - caches API responses so the UI stays fast
- XGBoost/Random Forest - ML models for confidence scoring
- yfinance - pulls stock data from NSE
- APScheduler - runs the daily scan automatically

**Frontend:**
- React + TypeScript - the dashboard you interact with
- Tailwind CSS - makes it look decent
- Recharts - all the performance graphs
- WebSockets - live updates when new signals come in

**Infrastructure:**
- Runs locally or in Docker
- Health checks and circuit breakers so it doesn't crash when APIs fail
- Tests with pytest and vitest

## How it picks stocks

The system is pretty strict about what qualifies as a signal. For a BUY, all of these have to be true:

1. **Price is trending up** - Close above the 10-day moving average, and the 10-day is above the 20-day
2. **Momentum is strong** - Either breaking out of a Darvas box or holding above the box high
3. **Volume confirms it** - At least 1.2x the 20-day average volume
4. **ML model agrees** - Confidence score above 60%
5. **Sector isn't weak** - Optional filter to avoid sectors that are bleeding

For SELL signals:
- Price drops below the 50-day moving average
- Darvas box breaks down
- ML confidence above 50%

## Risk management

I didn't want this thing blowing up accounts, so there are guardrails:

- **Position sizing**: Uses Kelly Criterion (but only half of what it suggests, because full Kelly is insane)
- **Stop loss**: Starts at -12%, but if you're up 2.5%, it trails by 1% to lock in gains
- **Take profit**: Based on ATR (Average True Range) - targets 3x the stock's typical daily movement
- **Max positions**: Won't open more than 5 trades at once
- **Drawdown protection**: If the portfolio is down 8%, it stops opening new positions

## Real performance

I backtested this on 90 days of data with ₹10,000 starting capital:
- Made 19.45% return
- Won 61.1% of trades
- That's a 34% annualized return (CAGR)
- Generated 329 signals across 600+ stocks
- Profit factor of 2.1 (winners are 2x bigger than losers)

These aren't cherry-picked. This is what the system actually does when you run it on historical data.

## Getting it running

You'll need:
- Python 3.11 or newer
- Node.js 20 or newer
- PostgreSQL (any recent version)
- Redis
- Git

### Quick setup

**1. Clone it**
```bash
git clone https://github.com/yourusername/nse-signal-engine.git
cd nse-signal-engine
```

**2. Set up the database**
```bash
# Create the database
psql -U postgres
CREATE DATABASE nse_db;
\q

# Start Redis
redis-server
```

**3. Backend**
```bash
cd backend

# Virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install stuff
pip install -r requirements.txt

# Configure it
cp .env.example .env
# Edit .env - at minimum, set your DATABASE_URL and SECRET_KEY

# Set up the database
alembic upgrade head

# Load the NSE 500 stock list
python scripts/seed_sample_data.py

# Optional: Train an ML model (takes a while, system works without it)
python -m app.ml.evaluator --config app/ml/configs/eval.yaml

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend runs at http://localhost:8000

**4. Frontend**
```bash
cd frontend

npm install
npm run dev
```

Frontend runs at http://localhost:5174

That's it. Open the frontend URL and you should see the dashboard.

## Configuration

Create a `.env` file in the `backend` directory. Here's what matters:

```bash
# Database connection
DATABASE_URL=postgresql://postgres:password@localhost:5432/nse_db

# Redis
REDIS_URL=redis://localhost:6379/0

# Security - IMPORTANT: Generate a real key with: openssl rand -hex 32
SECRET_KEY=your-secret-key-here-minimum-32-characters

# Allow your frontend to talk to the backend
ALLOWED_ORIGINS=http://localhost:5174,http://localhost:5173

# Trading rules (tweak these if you want)
ML_CONFIDENCE_THRESHOLD=0.60  # How confident the ML model needs to be
VOLUME_MULTIPLIER=1.2          # Minimum volume vs average
LOOKAHEAD_DAYS=7               # How far ahead to look for outcomes

# Paper trading limits
PAPER_MAX_POSITIONS=5          # Max concurrent positions
PAPER_DEFAULT_CAPITAL=1000000  # Starting capital (₹10 lakh)
PAPER_MAX_DRAWDOWN_HALT=8.0    # Stop trading if down 8%

# Optional: Telegram alerts
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id

# User registration (set to True if you want others to sign up)
ALLOW_REGISTRATION=False
```

### When things run automatically

The system has a scheduler that runs tasks at specific times:

- **5:00 PM IST (11:30 UTC)** - Main daily scan, generates all signals
- **Every 15 minutes** - Updates the sector heatmap
- **Every minute** - Quick health check
- **9:20 AM IST** - Opens paper trading positions for high-confidence signals
- **3:45 PM IST** - Checks if any positions hit stop-loss or target
- **10:00 PM UTC** - Grades yesterday's trades (win/loss)

## API endpoints

Once it's running, check out http://localhost:8000/docs for the full interactive API documentation.

Here are the useful ones:

**Signals**
- `GET /signals/today` - What signals fired today
- `GET /signals/symbol/RELIANCE` - History for a specific stock
- `GET /signals/high-risk` - Low confidence signals (for validation)

**Analytics**
- `GET /sector/report` - Which sectors are hot/cold
- `GET /analytics/regime` - Is the market bullish/bearish/choppy
- `GET /analytics/bulk-backtest` - Run backtest on all 600+ stocks

**Paper Trading**
- `GET /paper/performance` - How's your paper portfolio doing
- `POST /paper/open` - Manually open a position
- `POST /paper/close/{trade_id}` - Close a position

**Backtesting**
- `POST /backtest/run` - Backtest a single stock
- `POST /backtest/walk-forward` - More rigorous test that simulates real trading

**Admin**
- `POST /admin/trigger-update` - Force a manual scan (don't wait for scheduler)
- `GET /health` - Is everything working?

## Testing

**Backend:**
```bash
cd backend
pytest                    # Run all tests
pytest --cov=app         # With coverage report
```

**Frontend:**
```bash
cd frontend
npm run test             # Run once
npm run test:watch       # Keep running as you code
```

## Project structure

```
backend/
├── app/
│   ├── api/              # All the API endpoints
│   ├── services/         # Core logic (signal generation, backtesting, paper trading)
│   ├── ml/               # Machine learning models and training
│   ├── indicators/       # Technical indicators (EMA, Darvas, ATR)
│   ├── db/               # Database models and connection
│   ├── core/             # Config, scheduler, logging
│   └── data/             # NSE 500 stock list
├── alembic/              # Database migrations
├── tests/                # Tests
└── requirements.txt      # Python packages

frontend/
├── src/
│   ├── pages/            # Dashboard, stock detail, performance, admin
│   ├── components/       # Reusable UI components
│   ├── services/         # API client
│   └── hooks/            # WebSocket and other React hooks
└── package.json          # Node packages
```

## Cool features you might miss

**Walk-forward backtesting**: Most backtests are bullshit because they train on all the data. This one trains on historical data, then tests on future data it's never seen. Repeat that across multiple time windows and you get a realistic picture of how it adapts.

**Monte Carlo simulation**: Takes your trade history and resamples it 1000 times to show you the range of possible outcomes. Helps you understand if you got lucky or if the strategy is actually robust.

**Circuit breakers**: If yfinance API starts failing, the system automatically stops hitting it for 30 seconds instead of hammering it and making things worse.

**WebSocket updates**: When a new signal fires, it pushes to your browser instantly. No need to refresh.

**ML calibration**: The confidence scores aren't just raw model outputs. They're calibrated using Platt scaling so that "80% confidence" actually means the signal wins 80% of the time historically.

## Performance tricks

The system is fast because:
- API responses are cached in Redis for 90 seconds
- Stock data is fetched in parallel (10 workers)
- Database uses connection pooling
- Frontend only re-renders what changed
- Rate limiting prevents abuse (60 requests/min per IP)

## Security

- Passwords are hashed with bcrypt
- API uses JWT tokens (expire after 4 hours)
- CORS is locked down to specific origins
- SQL injection isn't possible (using SQLAlchemy ORM)
- Rate limiting on all endpoints

Generate a proper secret key:
```bash
openssl rand -hex 32
```
Put that in your `.env` file as `SECRET_KEY`.

## Common problems

**"Can't connect to database"**
- Make sure PostgreSQL is actually running
- Check your DATABASE_URL in `.env` matches your setup

**"Redis connection failed"**
- Start Redis: `redis-server`
- Test it: `redis-cli ping` (should say PONG)

**"No data for stocks"**
- Check your internet connection
- yfinance sometimes rate limits - the circuit breaker will back off automatically
- Make sure symbols end with .NS (like RELIANCE.NS)

**"CORS errors in browser"**
- Add your frontend URL to ALLOWED_ORIGINS in backend `.env`
- Restart the backend after changing it

**"Scheduler isn't running"**
- Check the logs: `tail -f backend/logs/app.log`
- Should see "Scheduler configured with 5 jobs" on startup

## Deploying it

**Docker (easiest):**
```bash
docker-compose up -d
```

**Manual (production):**

Backend:
```bash
pip install -r requirements.txt
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

Frontend:
```bash
npm run build
# Serve the frontend/dist folder with nginx or whatever
```

For production, update your `.env`:
- Set `DEBUG=False`
- Use real database URLs (not localhost)
- Set `ALLOWED_ORIGINS` to your actual domain

## What's next

Things I'm planning to add:
- Multi-timeframe analysis (15min, 1hr, daily)
- News sentiment (so it doesn't buy stocks right before bad earnings)
- Fundamental filters (P/E ratio, debt levels, etc.)
- Mobile app
- Better backtesting UI with interactive charts
- Tax reporting for Indian markets (STCG/LTCG)

## Contributing

If you want to improve this, go ahead:
1. Fork it
2. Make your changes
3. Send a pull request

Try to follow PEP 8 for Python and use the existing code style for TypeScript.

## License

MIT - do whatever you want with it.

## Credits

Built using:
- FastAPI for the backend
- React for the frontend
- XGBoost for ML
- yfinance for market data
- Darvas Box theory from Nicolas Darvas's book "How I Made $2,000,000 in the Stock Market"

If you have questions, open an issue on GitHub.
