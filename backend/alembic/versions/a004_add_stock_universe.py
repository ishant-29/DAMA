"""add stock_universe table

Revision ID: a004_stock_universe
Revises: a003_market_holidays
Create Date: 2026-03-15

"""
from typing import Sequence, Union
from datetime import datetime, timezone
import csv
import os

from alembic import op
import sqlalchemy as sa

revision: str = 'a004_stock_universe'
down_revision: Union[str, Sequence[str], None] = 'a003_market_holidays'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'stock_universe',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('sector', sa.String(), nullable=True),
        sa.Column('industry', sa.String(), nullable=True),
        sa.Column('index_name', sa.String(), server_default='NIFTY500', nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=True),
        sa.Column('added_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('symbol'),
    )
    op.create_index('ix_stock_universe_symbol', 'stock_universe', ['symbol'])
    op.create_index('ix_stock_universe_sector', 'stock_universe', ['sector'])
    op.create_index('ix_stock_universe_index_name', 'stock_universe', ['index_name'])
    op.create_index('ix_stock_universe_is_active', 'stock_universe', ['is_active'])

    # Attempt to bulk-insert from nse500_list.csv if it exists
    csv_candidates = [
        os.path.join(os.path.dirname(__file__), '..', '..', 'app', 'data', 'nse500_list.csv'),
        os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'nse500_list.csv'),
    ]

    csv_path = None
    for candidate in csv_candidates:
        if os.path.isfile(candidate):
            csv_path = candidate
            break

    if csv_path:
        stock_table = sa.table(
            'stock_universe',
            sa.column('symbol', sa.String),
            sa.column('name', sa.String),
            sa.column('sector', sa.String),
            sa.column('industry', sa.String),
            sa.column('index_name', sa.String),
            sa.column('is_active', sa.Boolean),
            sa.column('added_at', sa.DateTime),
            sa.column('updated_at', sa.DateTime),
        )
        now = datetime.now(timezone.utc)
        rows = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                symbol = row.get('symbol', '').strip()
                if not symbol:
                    continue
                rows.append({
                    'symbol': symbol,
                    'name': row.get('company_name', row.get('name', '')).strip(),
                    'sector': row.get('sector', '').strip(),
                    'industry': row.get('industry', '').strip(),
                    'index_name': 'NIFTY500',
                    'is_active': True,
                    'added_at': now,
                    'updated_at': now,
                })

        if rows:
            op.bulk_insert(stock_table, rows)


def downgrade() -> None:
    op.drop_index('ix_stock_universe_is_active', table_name='stock_universe')
    op.drop_index('ix_stock_universe_index_name', table_name='stock_universe')
    op.drop_index('ix_stock_universe_sector', table_name='stock_universe')
    op.drop_index('ix_stock_universe_symbol', table_name='stock_universe')
    op.drop_table('stock_universe')
