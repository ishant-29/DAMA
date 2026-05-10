import os
import math
import pandas as pd
from collections import defaultdict
from typing import Dict, List, Any

class SectorService:
    def __init__(self):
        self.sector_map = {}
        self.sector_counts = {}
        self.load_sector_map()
        
    def load_sector_map(self):
        if self.sector_map:
            return

        # --- Strategy: DB first, CSV fallback ---
        try:
            from app.db.session import SessionLocal
            from app.db.models import SectorMapping

            db = SessionLocal()
            rows = db.query(SectorMapping).all()
            db.close()

            if rows:
                for r in rows:
                    sec = r.sector
                    if sec == "Automobile & Auto Components":
                        sec = "Automobile"
                    self.sector_map[r.symbol] = sec
                    self.sector_counts[sec] = self.sector_counts.get(sec, 0) + 1
                    # Support lookup without suffix
                    if r.symbol.endswith('.NS') or r.symbol.endswith('.BO'):
                        self.sector_map[r.symbol[:-3]] = sec
                print(f"Sector map loaded from DB ({len(rows)} entries)")
                return
            else:
                print("SectorMapping table empty, falling back to CSV")
        except Exception as e:
            print(f"DB sector load failed ({e}), falling back to CSV")

        # --- CSV fallback ---
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            csv_path = os.path.join(current_dir, '..', 'data', 'nse500_list.csv')
            
            if not os.path.exists(csv_path):
                print(f"Sector map not found at {csv_path}")
                return

            df = pd.read_csv(csv_path)
            df.columns = [c.lower().strip() for c in df.columns]
            
            for _, row in df.iterrows():
                if 'symbol' in row and 'sector' in row:
                    sym = str(row['symbol']).strip()
                    sec = str(row['sector']).strip()
                    if sec == "Automobile & Auto Components":
                        sec = "Automobile"
                    self.sector_map[sym] = sec
                    self.sector_counts[sec] = self.sector_counts.get(sec, 0) + 1
                    # Support lookup without suffix
                    if sym.endswith('.NS') or sym.endswith('.BO'):
                        self.sector_map[sym[:-3]] = sec
                    
        except Exception as e:
            print(f"Error loading sector map from CSV: {e}")

    def get_sector_momentum(self) -> List[Dict[str, Any]]:
        """
        Calculates 5-day return for all sectors.
        Returns detailed stats for all sectors.
        """
        self.load_sector_map()
        
        sector_returns = defaultdict(list)
        
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            data_path = os.path.join(current_dir, '..', 'data', 'market_cache.csv')
            
            if os.path.exists(data_path):
                df = pd.read_csv(data_path)
                df['date'] = pd.to_datetime(df['date'])
                df.sort_values(['symbol', 'date'], inplace=True)
                
                # Group by symbol and take last 5 days
                for sym, group in df.groupby('symbol'):
                    if len(group) < 2:
                        continue
                    
                    # Ensure enough data for 5 days, else use what's available
                    available_days = len(group)
                    lookback = min(5, available_days)
                    
                    # Calculate return: (Latest - Previous) / Previous
                    last_close = group.iloc[-1]['close']
                    prev_close = group.iloc[-lookback]['close']
                    
                    if prev_close == 0 or pd.isna(prev_close) or pd.isna(last_close):
                        continue
                        
                    pct_change = ((last_close - prev_close) / prev_close) * 100
                    
                    # Skip NaN/Infinity results
                    if math.isnan(pct_change) or math.isinf(pct_change):
                        continue
                    
                    # Resolve Sector
                    base_sym = sym.replace('.NS', '')
                    sec = self.sector_map.get(base_sym)
                    if not sec and sym in self.sector_map:
                        sec = self.sector_map[sym]
                    
                    if sec and sec != "Unknown":
                        sector_returns[sec].append(pct_change)
                        
        except Exception as e:
            print(f"Error calculating sector momentum: {e}")

        # Aggregate Results
        results = []
        for sec, rets in sector_returns.items():
            avg_return = sum(rets) / len(rets) if rets else 0.0
            results.append({
                "sector": sec,
                "avg_return": avg_return,
                "stock_count": len(rets)
            })
            
        return results

    def get_top_momentum_sectors(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Returns top 2 gainers and top 2 losers based on 5-day return.
        """
        all_sectors = self.get_sector_momentum()
        
        # Sort by return descending
        all_sectors.sort(key=lambda x: x['avg_return'], reverse=True)
        
        # Top 2 Gainers
        gainers = []
        for s in all_sectors:
            if s['avg_return'] > 0:
                gainers.append({
                    "sector": s['sector'],
                    "avg_return": round(s['avg_return'], 2),
                    "label": "Strong Momentum"
                })
            if len(gainers) >= 2:
                break
                
        # Top 2 Losers (Bottom of the list)
        losers = []
        # Reverse to find worst
        for s in reversed(all_sectors):
            if s['avg_return'] < 0:
                losers.append({
                    "sector": s['sector'],
                    "avg_return": round(s['avg_return'], 2),
                    "label": "Weak Momentum"
                })
            if len(losers) >= 2:
                break
                
        return {
            "top_gainers": gainers,
            "top_losers": losers
        }
