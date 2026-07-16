"""Add session_timeout_minutes column to admin_settings."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '006_session_timeout'
down_revision: Union[str, None] = '005_webhook_signing'
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('admin_settings',
        sa.Column('session_timeout_minutes', sa.Integer(), nullable=False, server_default='30'))


def downgrade() -> None:
    op.drop_column('admin_settings', 'session_timeout_minutes')