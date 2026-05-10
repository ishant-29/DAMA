"""add market_holidays table

Revision ID: a003_market_holidays
Revises: a002_user_settings
Create Date: 2026-03-15

"""
from typing import Sequence, Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision: str = 'a003_market_holidays'
down_revision: Union[str, Sequence[str], None] = 'a002_user_settings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'market_holidays',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('date', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('date'),
    )
    op.create_index('ix_market_holidays_date', 'market_holidays', ['date'])

    # Seed NSE holidays for 2025 and 2026
    holidays_table = sa.table(
        'market_holidays',
        sa.column('date', sa.String),
        sa.column('description', sa.String),
        sa.column('created_at', sa.DateTime),
        sa.column('created_by', sa.String),
    )
    now = datetime.now(timezone.utc)
    holidays = [
        # 2025 NSE holidays
        ('2025-01-26', 'Republic Day'),
        ('2025-02-26', 'Maha Shivaratri'),
        ('2025-03-14', 'Holi'),
        ('2025-03-31', 'Id-Ul-Fitr (Ramadan)'),
        ('2025-04-10', 'Shri Mahavir Jayanti'),
        ('2025-04-14', 'Dr. Baba Saheb Ambedkar Jayanti'),
        ('2025-04-18', 'Good Friday'),
        ('2025-05-01', 'Maharashtra Day'),
        ('2025-06-07', 'Bakri Id'),
        ('2025-08-15', 'Independence Day'),
        ('2025-08-16', 'Parsi New Year'),
        ('2025-08-27', 'Shri Ganesh Chaturthi'),
        ('2025-10-02', 'Mahatma Gandhi Jayanti / Dussehra'),
        ('2025-10-21', 'Diwali Laxmi Pujan'),
        ('2025-10-22', 'Diwali Balipratipada'),
        ('2025-11-05', 'Prakash Gurpurb Sri Guru Nanak Dev'),
        ('2025-12-25', 'Christmas'),
        # 2026 NSE holidays
        ('2026-01-26', 'Republic Day'),
        ('2026-02-17', 'Maha Shivaratri'),
        ('2026-03-20', 'Id-Ul-Fitr (Ramadan)'),
        ('2026-03-25', 'Holi'),
        ('2026-04-03', 'Good Friday'),
        ('2026-04-14', 'Dr. Baba Saheb Ambedkar Jayanti'),
        ('2026-05-01', 'Maharashtra Day'),
        ('2026-05-27', 'Bakri Id'),
        ('2026-08-15', 'Independence Day'),
        ('2026-08-18', 'Shri Ganesh Chaturthi'),
        ('2026-10-02', 'Mahatma Gandhi Jayanti'),
        ('2026-10-10', 'Dussehra'),
        ('2026-11-09', 'Diwali Laxmi Pujan'),
        ('2026-11-10', 'Diwali Balipratipada'),
        ('2026-11-25', 'Prakash Gurpurb Sri Guru Nanak Dev'),
        ('2026-12-25', 'Christmas'),
    ]

    op.bulk_insert(holidays_table, [
        {'date': d, 'description': desc, 'created_at': now, 'created_by': 'migration'}
        for d, desc in holidays
    ])


def downgrade() -> None:
    op.drop_index('ix_market_holidays_date', table_name='market_holidays')
    op.drop_table('market_holidays')
