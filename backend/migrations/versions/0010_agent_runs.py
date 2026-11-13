"""Agent runs: one orchestrated analysis of a case, with every step it took.

Revision ID: 0010
Create date: 2026-11-13

Reversible: downgrade drops the table. Nothing else is touched.
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE agent_runs (
            id          bigserial PRIMARY KEY,
            case_id     uuid NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            objective   text NOT NULL,
            model       text NOT NULL,
            status      text NOT NULL CHECK (status IN ('running', 'completed', 'incomplete', 'failed')),
            steps       jsonb NOT NULL DEFAULT '[]',
            result      jsonb NOT NULL DEFAULT '{}',
            error       text,
            started_at  timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz
        );
        CREATE INDEX agent_runs_case_idx ON agent_runs (case_id, started_at DESC);
        CREATE UNIQUE INDEX agent_runs_one_running ON agent_runs (case_id) WHERE status = 'running';
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_runs;")
