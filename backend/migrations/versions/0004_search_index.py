"""Search: English stemming for keyword search, and the model behind each embedding.

Revision ID: 0004
Create date: 2026-11-07

* tsv used the 'simple' configuration (no stemming), so "possessed" did not match
  "possession". Orders are written in English; use the 'english' configuration.
* embedding_model records which model produced each vector. Vectors from different models
  are not comparable, so search only uses vectors from the configured model.
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DROP INDEX IF EXISTS order_chunks_tsv_idx;
        ALTER TABLE order_chunks DROP COLUMN tsv;
        ALTER TABLE order_chunks ADD COLUMN tsv tsvector
            GENERATED ALWAYS AS (to_tsvector('english', text)) STORED;
        CREATE INDEX order_chunks_tsv_idx ON order_chunks USING gin (tsv);
        ALTER TABLE order_chunks ADD COLUMN embedding_model text;
        ALTER TABLE order_chunks ADD CONSTRAINT order_chunks_embedding_has_model
            CHECK (embedding IS NULL OR embedding_model IS NOT NULL);
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE order_chunks DROP CONSTRAINT IF EXISTS order_chunks_embedding_has_model;
        ALTER TABLE order_chunks DROP COLUMN IF EXISTS embedding_model;
        DROP INDEX IF EXISTS order_chunks_tsv_idx;
        ALTER TABLE order_chunks DROP COLUMN tsv;
        ALTER TABLE order_chunks ADD COLUMN tsv tsvector
            GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED;
        CREATE INDEX order_chunks_tsv_idx ON order_chunks USING gin (tsv);
    """)
