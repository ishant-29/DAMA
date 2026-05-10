"""add is_admin and system_config table

Revision ID: a001_system_config
Revises: 28868836ba60
Create Date: 2026-03-15

"""
from typing import Sequence, Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision: str = 'a001_system_config'
down_revision: Union[str, Sequence[str], None] = '28868836ba60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_admin to users table
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), server_default='false', nullable=True))

    # Create system_config table
    op.create_table(
        'system_config',
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('value', sa.String(), nullable=False),
        sa.Column('value_type', sa.String(), nullable=False, server_default='str'),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('updated_by', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('key'),
    )

    # Seed initial tax/system config rows
    system_config = sa.table(
        'system_config',
        sa.column('key', sa.String),
        sa.column('value', sa.String),
        sa.column('value_type', sa.String),
        sa.column('description', sa.String),
        sa.column('updated_at', sa.DateTime),
        sa.column('updated_by', sa.String),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(system_config, [
        {'key': 'STCG_RATE', 'value': '0.15', 'value_type': 'float',
         'description': 'Short-term capital gains tax rate', 'updated_at': now, 'updated_by': 'migration'},
        {'key': 'LTCG_RATE', 'value': '0.10', 'value_type': 'float',
         'description': 'Long-term capital gains tax rate', 'updated_at': now, 'updated_by': 'migration'},
        {'key': 'LTCG_EXEMPTION', 'value': '100000', 'value_type': 'float',
         'description': 'LTCG annual exemption in INR', 'updated_at': now, 'updated_by': 'migration'},
        {'key': 'STT_RATE', 'value': '0.001', 'value_type': 'float',
         'description': 'Securities Transaction Tax rate', 'updated_at': now, 'updated_by': 'migration'},
        {'key': 'SHORT_TERM_DAYS', 'value': '365', 'value_type': 'int',
         'description': 'Days threshold for short-term classification', 'updated_at': now, 'updated_by': 'migration'},
        {'key': 'STCG_RATE_FY26', 'value': '0.20', 'value_type': 'float',
         'description': 'STCG rate from FY2025-26 budget', 'updated_at': now, 'updated_by': 'migration'},
    ])


def downgrade() -> None:
    op.drop_table('system_config')
    op.drop_column('users', 'is_admin')
