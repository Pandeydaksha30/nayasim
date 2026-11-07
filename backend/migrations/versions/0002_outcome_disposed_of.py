"""Add the 'disposed_of' outcome.

Revision ID: 0002
Create date: 2026-11-07

Many HRERA orders end "the complaint is disposed of": closed with directions, or sent to
another forum (e.g. NCLT moratorium), without allowing or dismissing it on the merits. The
first real extraction runs found this; folding it into "other" would hide it from the backtest.
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE case_records DROP CONSTRAINT case_records_outcome_check;
        ALTER TABLE case_records ADD CONSTRAINT case_records_outcome_check CHECK (
            outcome IN ('allowed', 'partly_allowed', 'dismissed', 'disposed_of', 'withdrawn', 'other'));
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE case_records SET outcome = 'other' WHERE outcome = 'disposed_of';
        ALTER TABLE case_records DROP CONSTRAINT case_records_outcome_check;
        ALTER TABLE case_records ADD CONSTRAINT case_records_outcome_check CHECK (
            outcome IN ('allowed', 'partly_allowed', 'dismissed', 'withdrawn', 'other'));
    """)
