"""Add signing_secret column to webhook_config for HMAC signature verification."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '005_webhook_signing'
down_revision: Union[str, None] = '004_token_families'
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('webhook_config',
        sa.Column('signing_secret', sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column('webhook_config', 'signing_secret')