"""Add scope column to api_keys — read/write/admin scoping."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '003_api_key_scopes'
down_revision: Union[str, None] = '002_canary_tokens'
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('api_keys',
        sa.Column('scope', sa.String(32), nullable=False, server_default='admin'))
    op.create_index('ix_api_keys_scope', 'api_keys', ['scope'])


def downgrade() -> None:
    op.drop_index('ix_api_keys_scope')
    op.drop_column('api_keys', 'scope')