"""Add token_families table for multi-device logout revocation."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '004_token_families'
down_revision: Union[str, None] = '003_api_key_scopes'
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'token_families',
        sa.Column('family_id', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked', sa.Boolean(), nullable=False, default=False),
    )
    op.create_index('ix_token_families_user', 'token_families', ['user_id'])
    op.add_column('revoked_tokens',
        sa.Column('family_id', sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column('revoked_tokens', 'family_id')
    op.drop_index('ix_token_families_user')
    op.drop_table('token_families')