"""Hearing runs: one row per simulated hearing, with its full result.

Revision ID: 0006
Create date: 2026-11-07

A run belongs to a buyer case (live use) or to a stored order (backtest, step 9). The result
JSON keeps every argument, every citation verdict (kept or removed, with reasons), the
judge's view, the precedent statistics and the computed award, so a report can always be
traced back to what produced it.
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE hearing_runs (
            id          bigserial PRIMARY KEY,
            case_id     uuid   REFERENCES cases (id) ON DELETE CASCADE,
            order_id    bigint REFERENCES orders (id) ON DELETE CASCADE,
            cutoff      date   NOT NULL,
            models      text   NOT NULL,
            status      text   NOT NULL CHECK (status IN ('completed', 'failed')),
            error       text,
            result      jsonb  NOT NULL DEFAULT '{}',
            started_at  timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz,
            CONSTRAINT hearing_runs_subject CHECK ((case_id IS NULL) <> (order_id IS NULL)),
            CONSTRAINT hearing_runs_failed_has_error CHECK (status <> 'failed' OR error IS NOT NULL)
        );
        CREATE INDEX hearing_runs_case_idx ON hearing_runs (case_id, started_at DESC);
        CREATE INDEX hearing_runs_order_idx ON hearing_runs (order_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS hearing_runs;")
