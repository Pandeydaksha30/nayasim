"""Embedding size 1024 -> 384 for BAAI/bge-small-en-v1.5.

Revision ID: 0005
Create date: 2026-11-07

Measured on this laptop (with OCR running alongside, so absolute times are inflated):
bge-small 266 ms/chunk, bge-base 1,254 ms/chunk; bge-large was slower still and was stopped.
Orders are English, so an English model fits; keyword search covers exact legal terms.
No real embeddings existed yet, so clearing the column loses nothing.
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _resize(dim: int) -> None:
    op.execute(f"""
        DROP INDEX IF EXISTS order_chunks_embedding_idx;
        UPDATE order_chunks SET embedding = NULL, embedding_model = NULL WHERE embedding IS NOT NULL;
        ALTER TABLE order_chunks ALTER COLUMN embedding TYPE vector({dim}) USING NULL;
        CREATE INDEX order_chunks_embedding_idx ON order_chunks USING hnsw (embedding vector_cosine_ops);
    """)


def upgrade() -> None:
    _resize(384)


def downgrade() -> None:
    _resize(1024)
