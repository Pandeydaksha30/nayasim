"""Hearings run in the background: a run can be 'running' until it completes or fails.

Revision ID: 0008
Create date: 2026-11-10

- status may now be 'running' (finished_at stays NULL until it ends).
- At most one running hearing per case (a second click cannot start a duplicate).
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE hearing_runs DROP CONSTRAINT hearing_runs_status_check;
        ALTER TABLE hearing_runs ADD CONSTRAINT hearing_runs_status_check
            CHECK (status IN ('running', 'completed', 'failed'));
        ALTER TABLE hearing_runs ADD CONSTRAINT hearing_runs_finished_when_done
            CHECK (status = 'running' OR finished_at IS NOT NULL);
        CREATE UNIQUE INDEX hearing_runs_one_running_per_case
            ON hearing_runs (case_id) WHERE status = 'running';
    """)


def downgrade() -> None:
    op.execute("""
        DROP INDEX IF EXISTS hearing_runs_one_running_per_case;
        ALTER TABLE hearing_runs DROP CONSTRAINT IF EXISTS hearing_runs_finished_when_done;
        UPDATE hearing_runs SET status = 'failed', error = 'Interrupted', finished_at = now()
            WHERE status = 'running';
        ALTER TABLE hearing_runs DROP CONSTRAINT hearing_runs_status_check;
        ALTER TABLE hearing_runs ADD CONSTRAINT hearing_runs_status_check
            CHECK (status IN ('completed', 'failed'));
    """)
