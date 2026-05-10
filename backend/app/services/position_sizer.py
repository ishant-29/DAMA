"""
Kelly Criterion Position Sizing Engine.
Mathematically optimal position sizes based on edge and win rate.
"""

from dataclasses import dataclass
from typing import Optional

from app.core.config import settings


@dataclass
class PositionRecommendation:
    symbol: str
    kelly_fraction: float
    recommended_allocation: float
    max_shares: Optional[int]
    position_tier: str
    rationale: str


class KellyCriterionSizer:
    """
    Kelly Formula: f* = (bp - q) / b
    We use Half-Kelly (0.5 × f*) for safety.
    """

    MAX_POSITION_PCT = settings.POSITION_MAX_PCT
    MAX_SECTOR_PCT = settings.POSITION_MAX_SECTOR_PCT
    MAX_OPEN_POSITIONS = settings.PAPER_MAX_POSITIONS

    def calculate(
        self,
        confidence: float,
        reward_risk_ratio: float,
        portfolio_size: Optional[float] = None,
    ) -> PositionRecommendation:
        win_prob = confidence
        loss_prob = 1 - win_prob
        odds = reward_risk_ratio

        if odds <= 0:
            kelly = 0.0
        else:
            kelly = (odds * win_prob - loss_prob) / odds

        kelly = max(0.0, kelly)
        half_kelly = kelly * 0.5
        recommended = min(half_kelly, self.MAX_POSITION_PCT)

        if recommended >= 0.12:
            tier = "FULL"
            rationale = f"High edge signal — {recommended*100:.1f}% allocation"
        elif recommended >= 0.07:
            tier = "HALF"
            rationale = f"Medium edge — {recommended*100:.1f}% allocation"
        elif recommended >= 0.03:
            tier = "QUARTER"
            rationale = f"Low edge — small {recommended*100:.1f}% position only"
        else:
            tier = "SKIP"
            rationale = f"Edge too small ({kelly*100:.1f}% Kelly) — skip this signal"
            recommended = 0.0

        max_shares = None
        if portfolio_size and recommended > 0:
            max_shares = int(portfolio_size * recommended)

        return PositionRecommendation(
            symbol="",
            kelly_fraction=round(kelly, 4),
            recommended_allocation=round(recommended, 4),
            max_shares=max_shares,
            position_tier=tier,
            rationale=rationale,
        )

    def check_portfolio_heat(
        self,
        open_positions: int,
        portfolio_drawdown_pct: float,
        sector_exposure_pct: float,
    ) -> tuple:
        if open_positions >= self.MAX_OPEN_POSITIONS:
            return False, f"MAX_POSITIONS_REACHED ({open_positions}/{self.MAX_OPEN_POSITIONS})"
        if portfolio_drawdown_pct >= 8.0:
            return False, f"DRAWDOWN_HALT (drawdown={portfolio_drawdown_pct:.1f}% >= 8%)"
        if sector_exposure_pct >= self.MAX_SECTOR_PCT * 100:
            return False, f"SECTOR_LIMIT_REACHED ({sector_exposure_pct:.1f}% in sector)"
        return True, "POSITION_ALLOWED"


def add_position_sizing(signal_result: dict, sizer: KellyCriterionSizer) -> dict:
    """Attach position sizing recommendation to every BUY signal."""
    if signal_result.get('signal_type') != 'BUY':
        return signal_result

    confidence = signal_result.get('confidence', 0.65)
    rr = signal_result.get('reward_risk_ratio', 1.5)

    sizing = sizer.calculate(confidence=confidence, reward_risk_ratio=rr)

    signal_result['kelly_fraction'] = sizing.kelly_fraction
    signal_result['recommended_allocation_pct'] = sizing.recommended_allocation * 100
    signal_result['position_tier'] = sizing.position_tier
    signal_result['sizing_rationale'] = sizing.rationale

    return signal_result
