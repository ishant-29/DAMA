"""
Sector Rotation Engine — identifies top-performing NSE sectors.
BUY signals are only generated in the top 3 sectors by momentum.
"""

import math
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import yfinance as yf


# NSE Sector ETF/Index tickers for momentum calculation
SECTOR_TICKERS = {
    "IT": "^CNXIT",
    "BANK": "^NSEBANK",
    "PHARMA": "^CNXPHARMA",
    "AUTO": "^CNXAUTO",
    "FMCG": "^CNXFMCG",
    "METAL": "^CNXMETAL",
    "REALTY": "^CNXREALTY",
    "ENERGY": "^CNXENERGY",
    "INFRA": "^CNXINFRA",
    "MEDIA": "^CNXMEDIA",
    "PSU_BANK": "^CNXPSUBANK",
    "FINANCIAL": "^CNXFINANCE",
}


class SectorRotationEngine:

    @staticmethod
    def _safe_float(val: float) -> float:
        """Replace NaN/Infinity with 0.0 to ensure JSON serialization."""
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return 0.0
        return val

    def get_sector_momentum_scores(self, period: int = 5) -> Dict[str, dict]:
        """Calculates 5-day stock-average momentum for each sector."""
        from app.services.sector import SectorService
        service = SectorService()
        sector_stats = service.get_sector_momentum() # Returns list of {sector, avg_return, stock_count}
        
        scores = {}
        for stat in sector_stats:
            sector = stat['sector']
            avg_ret = self._safe_float(stat['avg_return'])
            scores[sector] = {
                'absolute_momentum': round(avg_ret, 2),
                'relative_momentum': round(avg_ret, 2), # Simplified to match heatmap absolute values
                'score': round(avg_ret, 2),
            }
            
        return scores

    def get_top_sectors(self, n: int = 3) -> List[str]:
        """Returns the top N sectors by relative momentum."""
        scores = self.get_sector_momentum_scores()
        sorted_sectors = sorted(scores.items(), key=lambda x: x[1]['score'], reverse=True)
        return [sector for sector, _ in sorted_sectors[:n]]

    def is_sector_favorable(self, sector: str, top_n: int = 3) -> Tuple[bool, float]:
        """Returns (is_top_sector, sector_momentum_score)."""
        scores = self.get_sector_momentum_scores()
        top_sectors = self.get_top_sectors(top_n)

        sector_upper = sector.upper()
        for key, val in scores.items():
            if key.upper() in sector_upper or sector_upper in key.upper():
                return key in top_sectors, val['score']

        return False, 0.0

    def get_full_report(self) -> dict:
        """Full sector momentum report for dashboard display."""
        scores = self.get_sector_momentum_scores()
        top_sectors = self.get_top_sectors(3)

        sector_list = [
            {
                'sector': sector,
                'absolute_momentum': data['absolute_momentum'],
                'relative_momentum': data['relative_momentum'],
                'is_top_sector': sector in top_sectors,
                'rank': idx + 1,
            }
            for idx, (sector, data) in enumerate(
                sorted(scores.items(), key=lambda x: x[1]['score'], reverse=True)
            )
        ]

        return {
            'top_sectors': top_sectors,
            'all_sectors': sector_list,
            'last_updated': pd.Timestamp.now().isoformat(),
        }
