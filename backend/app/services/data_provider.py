import yfinance as yf
import pandas as pd
import os
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.core.config import settings
from app.services.circuit_breaker import get_circuit_breaker, CircuitBreakerOpenError

logger = logging.getLogger(__name__)

DATA_DIR = settings.DATA_DIR
NSE_LIST_PATH = os.path.join(DATA_DIR, "nse500_list.csv")

# Circuit breaker for yfinance API
yfinance_circuit_breaker = get_circuit_breaker(
    name="yfinance",
    failure_threshold=5,
    recovery_timeout=30.0,
)

import threading

# Rate limiting for yfinance
_last_request_time = 0.0
_min_request_interval = 1.0 / (settings.YFINANCE_RATE_LIMIT / 3600)  # seconds between requests

# In-memory cache for DataFrame results
_df_cache = {}
CACHE_TTL_SECONDS = 3600  # 1 hour

# Thread locks to prevent concurrent fetching of the same symbol
_symbol_locks = {}
_global_lock = threading.Lock()

def _get_symbol_lock(symbol: str):
    with _global_lock:
        if symbol not in _symbol_locks:
            _symbol_locks[symbol] = threading.Lock()
        return _symbol_locks[symbol]


def _rate_limit_yfinance():
    """Apply rate limiting to yfinance calls."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < _min_request_interval:
        time.sleep(_min_request_interval - elapsed)
    _last_request_time = time.time()


def get_nse_500_list():
    """Reads the NSE 500 list from CSV."""
    if not os.path.exists(NSE_LIST_PATH):
        logger.error(f"NSE list not found at {NSE_LIST_PATH}")
        return []
    
    try:
        df = pd.read_csv(NSE_LIST_PATH)
        if 'symbol' in df.columns:
            return df['symbol'].tolist()
        return []
    except Exception as e:
        logger.error(f"Error reading NSE list: {e}")
        return []


def fetch_ticker_data(symbol: str, period: str = "1y", interval: str = "1d"):
    """
    Fetches historical data for a single symbol using yfinance.
    Protected by circuit breaker, rate limiting, and in-memory caching.
    """
    cache_key = f"{symbol}:{period}:{interval}"
    
    # Fast path: unlocked cache check
    if cache_key in _df_cache:
        cached_df, timestamp = _df_cache[cache_key]
        if time.time() - timestamp < CACHE_TTL_SECONDS:
            return cached_df.copy()

    # If not in cache, acquire lock for this specific symbol
    with _get_symbol_lock(symbol):
        # Double check cache inside lock (in case another thread just fetched it)
        if cache_key in _df_cache:
            cached_df, timestamp = _df_cache[cache_key]
            if time.time() - timestamp < CACHE_TTL_SECONDS:
                return cached_df.copy()

        try:
            # Check circuit breaker first
            if yfinance_circuit_breaker.state.value == "open":
                logger.warning(f"Circuit breaker OPEN for yfinance, skipping {symbol}")
                return None
            
            # Apply rate limiting
            _rate_limit_yfinance()
        
            # yfinance expects symbols like 'RELIANCE.NS' for NSE or 'RELIANCE.BO' for BSE
            if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
                symbol = f"{symbol}.NS"
                
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                logger.warning(f"No data found for {symbol}")
                return None
                
            df.reset_index(inplace=True)
            df.columns = [c.lower() for c in df.columns]
            
            if 'date' in df.columns:
                df['date'] = df['date'].dt.tz_localize(None)
                
            # Store in cache
            _df_cache[cache_key] = (df.copy(), time.time())
                
            return df
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None

def fetch_all_data_map(symbols, max_workers=None, period="1y", interval="1d") -> dict[str, pd.DataFrame]:
    """
    Fetches data for all symbols and returns a map of {symbol: dataframe}.
    """
    data_map = {}
    
    with ThreadPoolExecutor(max_workers=max_workers or settings.DATA_FETCH_WORKERS) as executor:
        future_to_symbol = {executor.submit(fetch_ticker_data, sym, period, interval): sym for sym in symbols}
        
        for future in as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                df = future.result()
                if df is not None and not df.empty:
                    # Strip .NS for consistency with internal app logic if needed, 
                    # but SignalEngine expects keys to match what's in the list.
                    # The nse500_list.csv has .NS suffix? Let's check.
                    # Yes, file view showed "RELIANCE.NS".
                    # fetch_ticker_data adds .NS if missing.
                    # We should key it by the symbol passed in.
                    data_map[symbol] = df
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                
    return data_map
