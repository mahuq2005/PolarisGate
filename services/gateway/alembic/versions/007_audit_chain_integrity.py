"""Add HMAC chain integrity columns to audit_logs for tamper-evident logging.

Each audit entry gets:
  - chain_hash: HMAC-SHA256(previous_entry.chain_hash || current_entry_data)
  - prev_hash: link to previous entry's chain_hash

A broken chain means the audit log has been tampered with.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '007_audit_chain_integrity'
down_revision: Union[str, None] = '006_session_timeout'
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('audit_logs',
        sa.Column('chain_hash', sa.String(64), nullable=True))
    op.add_column('audit_logs',
        sa.Column('prev_hash', sa.String(64), nullable=True))
    op.create_index('ix_audit_logs_chain', 'audit_logs', ['chain_hash'])


def downgrade() -> None:
    op.drop_index('ix_audit_logs_chain')
    op.drop_column('audit_logs', 'prev_hash')
    op.drop_column('audit_logs', 'chain_hash')