import pandas as pd
import numpy as np
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models import Signal
from app.indicators.ema import ema_df
from app.indicators.darvas import darvas_boxes
from app.ml.preprocessor import Preprocessor
from app.ml.ml_models.xgboost_model import XGBoostModel 
from app.ml.ml_models.random_forest_model import RandomForestModel
import logging
import os
import joblib
logger = logging.getLogger(__name__)

from app.services.feedback import FeedbackService
from app.core.config import settings
from app.core.logging import logger

class SignalEngine:
    def __init__(self, db: Session):
        self.db = db
        self.preprocessor = Preprocessor()
        
        # Dynamic Model Path Finding
        artifacts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'artifacts')
        self.model_path = None
        self.model_type = 'xgboost' # default
        
        try:
            # Look for ANY .pkl model
            files = [f for f in os.listdir(artifacts_dir) if f.endswith('.pkl')]
            if files:
                # Sort by reverse alphabetical (assuming timestamp is in name)
                # e.g. random_forest_model__v2025... vs xgboost_model...
                files.sort(reverse=True)
                self.model_path = os.path.join(artifacts_dir, files[0])
                logger.debug(f"Found latest model: {self.model_path}")
                logger.debug(f"Model path set to {self.model_path}, type {self.model_type}")
                
                if 'random_forest' in files[0]:
                    self.model_type = 'random_forest'
                else:
                    self.model_type = 'xgboost'
                    
        except Exception as e:
            logger.debug(f"Error finding model: {e}")
            
        self.sell_confidence_threshold = float(os.getenv("SELL_CONFIDENCE_THRESHOLD", 0.50))
        self.sector_threshold = float(os.getenv("SECTOR_THRESHOLD", 0.0))
        
        # Dynamic Config
        feedback_service = FeedbackService(db)
        self.ml_confidence_threshold, self.volume_multiplier = feedback_service.get_current_thresholds()
        
        # Load Sector Map
        try:
             import pandas as pd
             # Robust path resolution
             current_dir = os.path.dirname(os.path.abspath(__file__))
             # SignalEngine is in app/services. Data is in app/data.
             csv_path = os.path.join(current_dir, '..', 'data', 'nse500_list.csv')
             
             meta_df = pd.read_csv(csv_path)
             # Clean strings
             meta_df.columns = [c.lower().strip() for c in meta_df.columns]
             
             # Create map: Symbol -> Sector
             # Ensure symbols are stripped
             symbol_col = meta_df['symbol'].astype(str).str.strip()
             sector_col = meta_df['sector'].astype(str).str.strip()
             
             self.sector_map = dict(zip(symbol_col, sector_col))
        except Exception as e:
            print(f"Failed to load sector map from {os.getcwd()}: {e}")
            logger.debug("Sector map load attempted, result: " + ("success" if hasattr(self, 'sector_map') else "failure"))
            self.sector_map = {}


    def calculate_technical_confidence(self, df: pd.DataFrame, signal_type: str, sector_score: float = 0.0) -> float:
        """
        Calculates a heuristic confidence score (0.0 - 1.0) based on technical strength.
        Uses configuration constants for all magic numbers.
        """
        score = settings.SIGNAL_BASE_SCORE
        
        try:
            latest = df.iloc[-1]
            # 1. Trend Strength (EMA Divergence)
            if signal_type == "BUY":
                ema_50 = latest.get('ema_50', float('nan'))
                if not pd.isna(ema_50) and ema_50 > 0:
                    divergence = (latest['close'] - ema_50) / ema_50
                    score += min(settings.SIGNAL_EMA_DIVERGENCE_BONUS_MAX, divergence * 2) 
            elif signal_type == "SELL":
                ema_50 = latest.get('ema_50', float('nan'))
                if not pd.isna(ema_50) and ema_50 > 0:
                    divergence = (ema_50 - latest['close']) / ema_50
                    score += min(settings.SIGNAL_EMA_DIVERGENCE_BONUS_MAX, divergence * 2)

            # 2. Volume Confirmation
            if 'volume' in df.columns:
                avg_vol = df['volume'].rolling(20).mean().iloc[-1]
                if not pd.isna(avg_vol) and avg_vol > 0:
                    vol_ratio = latest['volume'] / avg_vol
                    if vol_ratio > 1.5:
                        score += settings.SIGNAL_VOLUME_BONUS_1_5X
                    if vol_ratio > 2.0:
                        score += settings.SIGNAL_VOLUME_BONUS_2_0X

            # 3. Momentum (Consecutive Candles)
            if len(df) >= 3:
                last_3 = df.iloc[-3:]
                if 'open' in df.columns and 'close' in df.columns:
                    if signal_type == "BUY":
                        greens = sum(1 for i in range(3) if last_3.iloc[i]['close'] > last_3.iloc[i].get('open', float('inf')))
                        score += (greens * settings.SIGNAL_MOMENTUM_BONUS_PER_CANDLE)
                    elif signal_type == "SELL":
                        reds = sum(1 for i in range(3) if last_3.iloc[i]['close'] < last_3.iloc[i].get('open', float('-inf')))
                        score += (reds * settings.SIGNAL_MOMENTUM_BONUS_PER_CANDLE)
            
            # 4. Sector Momentum Bonus
            if sector_score > 0:
                sector_bonus = min(settings.SIGNAL_SECTOR_MOMENTUM_BONUS_MAX, max(0, sector_score)) 
                score += sector_bonus

        except Exception as e:
            logger.error(f"Error calculating technical confidence: {e}")
        
        return min(settings.SIGNAL_CONFIDENCE_MAX, max(settings.SIGNAL_CONFIDENCE_MIN, score))

    def load_model_instance(self):
        if self.model_type == 'random_forest':
            return RandomForestModel()
        else:
            return XGBoostModel() # Default
        
    def analyze_symbol(self, symbol: str, df: pd.DataFrame, sector_scores: dict, model=None, has_model=False) -> dict:
        """
        Analyze a single symbol and return its detailed status (Signal, Confidence, Reasons).
        Always returns a result, never skips.
        """
        try:
            # Optimize: Limit to last 300 bars for analysis (enough for trend/darvas)
            # data is already sorted? same as before
            df = df.sort_values('date').tail(300).reset_index(drop=True)
            
            # 1. Calculate Indicators
            df = ema_df(df, [10, 20, 50])
            df = darvas_boxes(df)
            
            # Get latest bar
            latest = df.iloc[-1]
            
            # Strict Rules
            
            # BUY CONDITIONS
            # BUY CONDITIONS
            is_above_ema10 = (latest['close'] > latest.get('ema_10', float('inf'))) # Fail safe: if broken, don't buy
            is_breakout = bool(latest.get('darvas_breakout', False))
            
            # Broaden: Also check if holding above the box level (Trending)
            # Handle NaN safely
            box_high = latest.get('darvas_high', float('nan'))
            is_holding_trend = False
            if not pd.isna(box_high):
                is_holding_trend = (latest['close'] >= box_high)

            cond_buy_strict = is_above_ema10 and (is_breakout or is_holding_trend)
            logger.debug(f"BUY strict condition: {cond_buy_strict}, EMA10 above: {is_above_ema10}, breakout: {is_breakout}, holding_trend: {is_holding_trend}")

            # SELL CONDITIONS
            # Check if ema_50 exists, if not, assume we are NOT below it (safe default) or handle as neutral
            ema_50_val = latest.get('ema_50', float('-inf'))
            is_below_ema50 = False
            if not pd.isna(ema_50_val) and ema_50_val != float('-inf'):
                 is_below_ema50 = (latest['close'] < ema_50_val)
                 
            is_breakdown = bool(latest.get('darvas_breakdown', False))
            # Only consider breakdown, not holding within box
            cond_sell_strict = is_below_ema50 and is_breakdown
            logger.debug(f"SELL strict condition: {cond_sell_strict}, EMA50 below: {is_below_ema50}, breakdown: {is_breakdown}")
            
            signal_type = "NEUTRAL"
            reason = {
            "ema_condition": is_above_ema10, # For display purposes, showing if trend is good
            "darvas_condition": is_breakout or is_holding_trend, # For display purposes, showing if Darvas is good
            "message": "Neutral"
            }
            
            if cond_buy_strict:
                signal_type = "BUY"
                trend_msg = "bullish_breakout" if is_breakout else "bullish_trend"
                reason = {
                    "ema_condition": True, 
                    "darvas_condition": True,
                    "trend": trend_msg
                }
            elif cond_sell_strict:
                signal_type = "SELL"
                reason = {
                    "ema_condition": True, 
                    "darvas_condition": True,
                    "trend": "bearish_breakdown"
                }
            
            # Calculate Confidence for EVERYONE (User Request)
            # Even if Neutral, calculate what the score WOULD be if we assessed technicals
            
            # Get sector score first (needed for confidence calculation)
            sector_name = "Unknown"
            if hasattr(self, 'sector_map') and symbol in self.sector_map:
                sector_name = self.sector_map[symbol]
            sector_score = float(sector_scores.get(sector_name, 0.5)) if sector_scores else 0.5
            
            confidence = 0.0
            is_potential = False  # Indicates if confidence is for potential (not actual signal)
            try:
                # For NEUTRAL signals, we still calculate confidence as "potential" score for display
                # but flag it so frontend knows it's not an actual signal
                if signal_type == "NEUTRAL":
                    is_potential = True
                    eval_type = "SELL" if is_below_ema50 else "BUY"
                else:
                    eval_type = signal_type
                
                if has_model:
                    X, _, _ = self.preprocessor.process_bars(df)
                    if not X.empty:
                        X_latest = X.iloc[[-1]] 
                        preds = model.predict(self.model_path, X_latest)
                        confidence = float(preds[0]) if len(preds) > 0 else 0.0
                else:
                    # Pass sector_score to confidence calculation
                    confidence = self.calculate_technical_confidence(df, eval_type, sector_score)
                logger.debug(f"Calculated confidence: {confidence} for eval_type {eval_type} with sector_score {sector_score}")
                    
            except Exception as e:
                logger.error(f"ML/Conf Error for {symbol}: {e}")
                confidence = 0.0

            # ── News Sentiment Integration ─────────────────
            news_data = {}
            try:
                from app.services.news_sentiment import NewsSentimentAnalyzer
                news_analyzer = NewsSentimentAnalyzer()
                news_result = news_analyzer.get_signal_sentiment(symbol)
                news_modifier = news_result.get('confidence_modifier', 0.0)
                confidence = max(0.0, min(1.0, confidence + news_modifier))
                news_data = {
                    'sentiment': news_result.get('sentiment', 'NEUTRAL'),
                    'modifier': news_modifier,
                    'articles': news_result.get('article_count', 0),
                }
                # Suppress BUY on strongly negative news
                if signal_type == "BUY" and news_result.get('sentiment') == 'STRONGLY_NEGATIVE':
                    signal_type = "NEUTRAL"
                    reason['suppressed_by_news'] = True
                    logger.info(f"[{symbol}] BUY suppressed — strongly negative news")
            except Exception as e:
                logger.debug(f"News sentiment skipped for {symbol}: {e}")

            # ── Fundamental Data Integration ───────────────
            fundamental_data = {}
            try:
                from app.services.fundamental_data import FundamentalDataFetcher
                fund_fetcher = FundamentalDataFetcher()
                fund_result = fund_fetcher.fetch(symbol)
                fund_score = fund_result.get('fundamental_score', 0.5)
                fund_grade = fund_result.get('fundamental_grade', 'C')
                # Bonus for strong fundamentals
                if fund_grade in ('A', 'B') and signal_type == "BUY":
                    confidence = min(1.0, confidence + 0.03)
                fundamental_data = {
                    'score': fund_score,
                    'grade': fund_grade,
                    'pe': fund_result.get('pe_ratio'),
                }
            except Exception as e:
                logger.debug(f"Fundamental data skipped for {symbol}: {e}")
            
            # Volume Check
            avg_vol = 0.0
            vol_ratio = 0.0
            
            if 'volume' in df.columns:
                try:
                     avg_vol = df['volume'].rolling(20).mean().iloc[-1]
                     if avg_vol > 0:
                         vol_ratio = latest['volume'] / avg_vol
                except Exception:
                    pass
            
            vol_valid = (vol_ratio >= self.volume_multiplier)
            
            # Handle NaN/Inf safely for JSON
            def safe_float(val):
                if pd.isna(val): return 0.0
                try:
                    vf = float(val)
                    if np.isinf(vf): return 0.0
                    return vf
                except: return 0.0

            reason['vol_ratio'] = round(safe_float(vol_ratio), 2)

            # Determine High Risk Status
            is_high_risk = False
            if signal_type == "BUY":
                 if confidence < self.ml_confidence_threshold:
                     is_high_risk = True
                 if not vol_valid:
                     is_high_risk = True # Low Volume = High Risk (instead of rejection)

            elif signal_type == "SELL":
                  if confidence < self.sell_confidence_threshold:
                      is_high_risk = True
                  if not vol_valid:
                      is_high_risk = True # Low Volume also considered high risk for SELL

            if is_high_risk:
                reason['is_high_risk'] = True # Tag it
            
            logger.debug(f"Signal {signal_type} high risk: {is_high_risk}, confidence: {confidence}, vol_valid: {vol_valid}")
            
            # Sanitize timestamp to reflect NSE market close (15:30 IST / 10:00 UTC)
            ts = latest['date']
            if pd.isna(ts):
                ts = None
            elif hasattr(ts, 'to_pydatetime'):
                ts = ts.to_pydatetime()
                if ts.hour == 0 and ts.minute == 0:
                    ts = ts.replace(hour=10, minute=0)
            
            # Sanitize reason dict values
            safe_reason = {}
            for k, v in reason.items():
                if isinstance(v, (bool, np.bool_)):
                    safe_reason[k] = bool(v)
                elif isinstance(v, (int, np.integer)):
                    safe_reason[k] = int(v)
                elif isinstance(v, (float, np.floating)):
                    safe_reason[k] = float(v)
                    if pd.isna(safe_reason[k]): safe_reason[k] = 0.0
                else:
                    safe_reason[k] = v

            result = {
                "symbol": symbol,
                "timestamp": ts,
                "signal_type": signal_type,
                "confidence": round(safe_float(confidence), 2),
                "is_potential": is_potential,  # Indicates if confidence is for potential (not actual signal)
                "reason": safe_reason,
                "sector_score": safe_float(sector_score),
                "is_high_risk": bool(is_high_risk),
                "vol_valid": bool(vol_valid),
            }
            if news_data:
                result['news_sentiment'] = news_data
            if fundamental_data:
                result['fundamentals'] = fundamental_data
            return result
        except Exception as e:
             import traceback
             traceback.print_exc()
             return {
                "symbol": symbol,
                "timestamp": None,
                "signal_type": "NEUTRAL",
                "confidence": 0.0,
                "reason": {"message": f"System Error: {str(e)}"},
                "sector_score": 0.0,
                "is_high_risk": False,
                "vol_valid": False
            }

    def generate_signals(self, symbols: list[str], data_map: dict[str, pd.DataFrame]) -> list[Signal]:
        """
        Generate signals for a list of symbols given their data.
        Enforces STRICT TRADING RULES.
        """
        signals = []
        
        # Load model if available
        model = self.load_model_instance()
        has_model = False
        try:
             # Try early load check
             if self.model_path and os.path.exists(self.model_path):
                 model.load(self.model_path)
                 has_model = True
                 logger.debug(f"Model loaded for inference: {self.model_type}")
        except Exception as e:
            logger.debug(f"Failed to load model init: {e}")
            pass

        # Real Sector Scoring Implementation
        # 1. Calculate Average 5-Day Return per Sector
        from collections import defaultdict
        sector_returns = defaultdict(list)
        
        for sym, df_data in data_map.items():
            if df_data is None or len(df_data) < 5:
                continue
            try:
                # Ensure sorted
                p_close = df_data['close'].values
                if len(p_close) >= 5:
                    last_c = p_close[-1]
                    prev_c = p_close[-5]
                    if prev_c > 0:
                        ret = (last_c - prev_c) / prev_c
                        
                        sec = "Unknown"
                        if hasattr(self, 'sector_map') and sym in self.sector_map:
                            sec = self.sector_map[sym]
                        
                        if sec != "Unknown":
                            sector_returns[sec].append(ret)
            except Exception as e:
                pass

        # 2. Compute Averages & Normalize
        avg_sector_ret = {}
        for sec, rets in sector_returns.items():
             if rets:
                 avg_sector_ret[sec] = sum(rets) / len(rets)
                 
        final_sector_scores = {}
        if avg_sector_ret:
            min_ret = min(avg_sector_ret.values())
            max_ret = max(avg_sector_ret.values())
            rng = max_ret - min_ret if (max_ret - min_ret) != 0 else 1.0
            for sec, val in avg_sector_ret.items():
                norm = 0.1 + ((val - min_ret) / rng) * 0.8
                final_sector_scores[sec] = norm
        
        for symbol in symbols:
            df = data_map.get(symbol)
            if df is None or len(df) < 50:
                continue
                
            # Use new Analysis Method
            analysis = self.analyze_symbol(symbol, df, final_sector_scores, model, has_model)
            
            # Logic to decide if we PERSIST this signal
            if analysis['signal_type'] == "NEUTRAL":
                continue
                
                 
            # Deduplication Check
            existing_signal = self.db.query(Signal).filter(
                Signal.symbol == symbol,
                Signal.timestamp == analysis['timestamp'],
                Signal.signal_type == analysis['signal_type']
            ).first()

            if existing_signal:
                continue
            
            # Persist
            sig = Signal(
                uuid=str(uuid.uuid4()),
                symbol=symbol,
                timestamp=analysis['timestamp'],
                recommendation_date=analysis['timestamp'],
                signal_type=analysis['signal_type'],
                reason=analysis['reason'],
                confidence=analysis['confidence'],
                sector_score=analysis['sector_score'],
                model_version=f"v1_{self.model_type}"
            )
            self.db.add(sig)
            signals.append(sig)
            
            # Batch commit
            if len(signals) % 10 == 0:
                try:
                    self.db.commit()
                except Exception:
                    self.db.rollback()
            
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()

        # Invalidate Redis cache so next API call gets fresh data
        if signals:
            import asyncio
            from app.services.cache_redis import invalidate
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(invalidate("signals:today:*"))
                else:
                    asyncio.run(invalidate("signals:today:*"))
            except Exception:
                pass  # Cache invalidation is best-effort

            # WebSocket broadcast for real-time frontend updates
            try:
                from app.api.websocket import manager as ws_manager
                for sig in signals:
                    signal_data = {
                        "uuid": sig.uuid,
                        "symbol": sig.symbol,
                        "signal_type": sig.signal_type,
                        "confidence": sig.confidence,
                        "sector_score": sig.sector_score,
                        "timestamp": str(sig.timestamp),
                        "reason": sig.reason,
                    }
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(ws_manager.broadcast_signal(signal_data))
            except Exception:
                pass  # WebSocket broadcast is best-effort

            # Telegram alerts for high-confidence BUY signals
            try:
                from app.services.notifier import send_signal_alert
                for sig in signals:
                    if sig.signal_type == "BUY" and sig.confidence >= 0.82:
                        signal_data = {
                            "symbol": sig.symbol,
                            "signal_type": sig.signal_type,
                            "confidence": sig.confidence,
                            "reason": sig.reason,
                            "sector": "",
                        }
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            loop.create_task(send_signal_alert(signal_data))
            except Exception:
                pass  # Telegram alert is best-effort

        return signals
