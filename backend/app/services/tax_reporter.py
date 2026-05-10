"""
Indian Tax Report Generator.
Generates STCG/LTCG trade-wise P&L statements for ITR filing.

Rules:
- STCG (< 12 months): configurable rate on gains
- LTCG (>= 12 months): configurable rate on gains above exemption
- STT already deducted at source
"""

import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models import PaperTrade, TradeStatus
from app.services.config_service import ConfigService


class TaxReporter:

    def generate_annual_report(self, db: Session, financial_year: str = None) -> dict:
        # Read tax params from DB (with settings.* fallback)
        stcg_rate = ConfigService.get_float("STCG_RATE", db, fallback=0.15)
        ltcg_rate = ConfigService.get_float("LTCG_RATE", db, fallback=0.10)
        ltcg_exemption = ConfigService.get_float("LTCG_EXEMPTION", db, fallback=100_000.0)
        short_term_days = ConfigService.get_int("SHORT_TERM_DAYS", db, fallback=365)

        if not financial_year:
            now = datetime.utcnow()
            fy_start_year = now.year if now.month >= 4 else now.year - 1
            financial_year = f"{fy_start_year}-{str(fy_start_year + 1)[2:]}"

        fy_year = int(financial_year.split('-')[0])
        fy_start = datetime(fy_year, 4, 1)
        fy_end = datetime(fy_year + 1, 3, 31, 23, 59, 59)

        closed_trades = (
            db.query(PaperTrade)
            .filter(
                PaperTrade.status != TradeStatus.OPEN,
                PaperTrade.exit_date >= fy_start,
                PaperTrade.exit_date <= fy_end,
            )
            .order_by(PaperTrade.exit_date)
            .all()
        )

        stcg_trades, ltcg_trades = [], []

        for trade in closed_trades:
            days = trade.holding_days or 0
            category = 'LTCG' if days >= short_term_days else 'STCG'

            record = {
                'symbol': trade.symbol,
                'entry_date': trade.entry_date.strftime('%d-%m-%Y') if trade.entry_date else '',
                'exit_date': trade.exit_date.strftime('%d-%m-%Y') if trade.exit_date else '',
                'quantity': trade.quantity,
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'holding_days': days,
                'cost_of_acquisition': round(trade.entry_price * trade.quantity, 2),
                'sale_consideration': round((trade.exit_price or 0) * trade.quantity, 2),
                'profit_loss': round(trade.pnl_amount or 0, 2),
                'category': category,
            }

            (stcg_trades if category == 'STCG' else ltcg_trades).append(record)

        stcg_gains = sum(t['profit_loss'] for t in stcg_trades if t['profit_loss'] > 0)
        stcg_losses = sum(t['profit_loss'] for t in stcg_trades if t['profit_loss'] < 0)
        stcg_net = stcg_gains + stcg_losses

        ltcg_gains = sum(t['profit_loss'] for t in ltcg_trades if t['profit_loss'] > 0)
        ltcg_losses = sum(t['profit_loss'] for t in ltcg_trades if t['profit_loss'] < 0)
        ltcg_net = ltcg_gains + ltcg_losses

        stcg_tax = max(0, stcg_net) * stcg_rate
        ltcg_taxable = max(0, ltcg_net - ltcg_exemption)
        ltcg_tax = ltcg_taxable * ltcg_rate
        total_tax = stcg_tax + ltcg_tax

        return {
            'financial_year': financial_year,
            'generated_at': datetime.utcnow().isoformat(),
            'summary': {
                'total_trades': len(closed_trades),
                'stcg_trades': len(stcg_trades),
                'ltcg_trades': len(ltcg_trades),
                'stcg_net_pnl': round(stcg_net, 2),
                'ltcg_net_pnl': round(ltcg_net, 2),
                'total_net_pnl': round(stcg_net + ltcg_net, 2),
                'estimated_stcg_tax': round(stcg_tax, 2),
                'estimated_ltcg_tax': round(ltcg_tax, 2),
                'total_estimated_tax': round(total_tax, 2),
                'ltcg_exemption_used': round(min(ltcg_gains, ltcg_exemption), 2),
            },
            'stcg_trades': stcg_trades,
            'ltcg_trades': ltcg_trades,
            'tax_notes': [
                "This report is for reference only — consult a CA for final tax filing",
                "STT already paid at source — do not add separately",
                "STCG losses can be set off against STCG/LTCG gains",
                f"LTCG exemption of ₹1,00,000 applied: ₹{min(ltcg_gains, ltcg_exemption):,.0f}",
            ],
        }

    def export_to_csv(self, report: dict) -> str:
        all_trades = report['stcg_trades'] + report['ltcg_trades']
        if not all_trades:
            return "No trades to export"
        df = pd.DataFrame(all_trades)
        return df.to_csv(index=False)

