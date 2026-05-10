"""add user_settings table

Revision ID: a002_user_settings
Revises: a001_system_config
Create Date: 2026-03-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a002_user_settings'
down_revision: Union[str, Sequence[str], None] = 'a001_system_config'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('stop_loss_pct', sa.Float(), server_default='0.05', nullable=True),
        sa.Column('take_profit_pct', sa.Float(), server_default='0.10', nullable=True),
        sa.Column('position_size_pct', sa.Float(), server_default='0.10', nullable=True),
        sa.Column('initial_capital', sa.Float(), server_default='1000000.0', nullable=True),
        sa.Column('min_confidence', sa.Float(), server_default='0.60', nullable=True),
        sa.Column('max_positions', sa.Integer(), server_default='5', nullable=True),
        sa.Column('kelly_fraction', sa.Float(), server_default='0.50', nullable=True),
        sa.Column('commission_rate', sa.Float(), server_default='0.001', nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id'),
    )
    op.create_index('ix_user_settings_user_id', 'user_settings', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_user_settings_user_id', table_name='user_settings')
    op.drop_table('user_settings')
