"""Search over a buyer's own uploaded documents: chunks with embeddings, and the questions asked.

Revision ID: 0009
Create date: 2026-11-13

A separate table from order_chunks, so a user's text and public orders can never be mixed by a
query. The owner is cases.user_id: every chunk carries case_id and is deleted with its case,
document or page. Reversible: downgrade drops both tables (uploaded files and page text stay).
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE case_document_chunks (
            id              bigserial PRIMARY KEY,
            case_id         uuid NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            document_id     uuid NOT NULL,
            page_no         int  NOT NULL,
            char_start      int  NOT NULL,
            char_end        int  NOT NULL,
            text            text NOT NULL,
            tsv             tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
            embedding       vector(384),
            embedding_model text,
            FOREIGN KEY (document_id, page_no)
                REFERENCES case_document_pages (document_id, page_no) ON DELETE CASCADE,
            CHECK (char_end > char_start AND char_start >= 0)
        );
        CREATE INDEX case_document_chunks_case_idx ON case_document_chunks (case_id);
        CREATE INDEX case_document_chunks_doc_idx ON case_document_chunks (document_id);
        CREATE INDEX case_document_chunks_tsv_idx ON case_document_chunks USING gin (tsv);
        CREATE INDEX case_document_chunks_embedding_idx
            ON case_document_chunks USING hnsw (embedding vector_cosine_ops);

        CREATE TABLE case_questions (
            id          bigserial PRIMARY KEY,
            case_id     uuid NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            question    text NOT NULL,
            result      jsonb NOT NULL,
            created_at  timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX case_questions_case_idx ON case_questions (case_id, created_at DESC);
    """)


def downgrade() -> None:
    op.execute("""
        DROP TABLE IF EXISTS case_questions;
        DROP TABLE IF EXISTS case_document_chunks;
    """)
