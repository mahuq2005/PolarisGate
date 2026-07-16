"""Add canary token detection tables — CLLMSE Domain 5, §5.4.

Creates:
  canary_tokens   — planted decoy credentials (fake API keys)
  canary_alerts   — detection events when a canary is triggered
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002_canary_tokens'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'canary_tokens',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('label', sa.String(255), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('token_value_encrypted', sa.Text(), nullable=False),
        sa.Column('placement', sa.String(32), nullable=False, default='system_prompt'),
        sa.Column('status', sa.String(16), nullable=False, default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(255), nullable=False),
    )
    op.create_index('ix_canary_tokens_status', 'canary_tokens', ['status'])
    op.create_index('ix_canary_tokens_hash', 'canary_tokens', ['token_hash'])

    op.create_table(
        'canary_alerts',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('token_id', sa.String(32), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source_text', sa.Text(), nullable=True),
        sa.Column('source_endpoint', sa.String(128), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=False, default=False),
        sa.ForeignKeyConstraint(['token_id'], ['canary_tokens.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_canary_alerts_token', 'canary_alerts', ['token_id'])
    op.create_index('ix_canary_alerts_detected', 'canary_alerts', ['detected_at'])


def downgrade() -> None:
    op.drop_table('canary_alerts')
    op.drop_table('canary_tokens')