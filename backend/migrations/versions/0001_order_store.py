"""Order store and buyer case tables.

Revision ID: 0001
Create date: 2026-11-07

Written as plain SQL so the rules are visible in one place. The database itself enforces
the project's ground rules wherever it can:

* every order page and chunk belongs to a stored order, and a chunk's offsets must
  describe exactly its own text (char_end - char_start = length of text);
* every buyer fact names its document, a page that exists in that document, and the
  character span it was read from;
* every download is logged, success or failure.
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

EMBEDDING_DIM = 1024  # BGE-M3 (multilingual: English + Hindi). Changing the model needs a migration.

UPGRADE = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ───────────── Order store (regulator orders) ─────────────

CREATE TABLE fetch_log (
    id           bigserial PRIMARY KEY,
    url          text        NOT NULL,
    fetched_at   timestamptz NOT NULL DEFAULT now(),
    http_status  integer,
    bytes        integer     CHECK (bytes >= 0),
    sha256       char(64),
    error        text,
    CONSTRAINT fetch_log_outcome_recorded CHECK (http_status IS NOT NULL OR error IS NOT NULL)
);

CREATE TABLE orders (
    id            bigserial PRIMARY KEY,
    source        text NOT NULL CHECK (source IN ('hrera_gurugram', 'hrera_panchkula', 'up_rera')),
    complaint_no  text NOT NULL,
    complainant   text,
    respondent    text,
    case_type     text NOT NULL,
    decided_on    date NOT NULL,
    pdf_url       text NOT NULL,
    pdf_sha256    char(64),
    page_count    integer CHECK (page_count > 0),
    text_source   text CHECK (text_source IN ('text_layer', 'ocr', 'mixed')),
    fetched_at    timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT orders_unique_decision UNIQUE (source, complaint_no, decided_on),
    CONSTRAINT orders_fetched_has_hash CHECK (fetched_at IS NULL OR pdf_sha256 IS NOT NULL)
);
-- Time-split backtest filters on decision date on every retrieval.
CREATE INDEX orders_decided_on_idx ON orders (decided_on);

CREATE TABLE order_pages (
    order_id        bigint  NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    page_no         integer NOT NULL CHECK (page_no >= 1),
    text            text    NOT NULL,
    text_source     text    NOT NULL CHECK (text_source IN ('text_layer', 'ocr')),
    ocr_engine      text,
    ocr_confidence  numeric(5, 2) CHECK (ocr_confidence BETWEEN 0 AND 100),
    PRIMARY KEY (order_id, page_no),
    CONSTRAINT order_pages_ocr_named CHECK (text_source = 'text_layer' OR ocr_engine IS NOT NULL)
);

CREATE TABLE order_chunks (
    id          bigserial PRIMARY KEY,
    order_id    bigint  NOT NULL,
    page_no     integer NOT NULL,
    char_start  integer NOT NULL CHECK (char_start >= 0),
    char_end    integer NOT NULL,
    text        text    NOT NULL,
    embedding   vector({EMBEDDING_DIM}),
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED,
    FOREIGN KEY (order_id, page_no) REFERENCES order_pages (order_id, page_no) ON DELETE CASCADE,
    CONSTRAINT order_chunks_span_matches_text CHECK (char_end - char_start = char_length(text))
);
CREATE INDEX order_chunks_order_idx ON order_chunks (order_id);
CREATE INDEX order_chunks_tsv_idx ON order_chunks USING gin (tsv);
CREATE INDEX order_chunks_embedding_idx ON order_chunks USING hnsw (embedding vector_cosine_ops);

-- One structured record per order, filled by extraction and checked by hand.
CREATE TABLE case_records (
    order_id           bigint PRIMARY KEY REFERENCES orders (id) ON DELETE CASCADE,
    claim_type         text NOT NULL CHECK (claim_type IN ('delayed_possession', 'refund', 'other')),
    outcome            text NOT NULL CHECK (outcome IN ('allowed', 'partly_allowed', 'dismissed', 'withdrawn', 'other')),
    possession_due     date,
    amount_paid        numeric(14, 2) CHECK (amount_paid >= 0),
    award_amount       numeric(14, 2) CHECK (award_amount >= 0),
    interest_rate_pct  numeric(6, 3)  CHECK (interest_rate_pct BETWEEN 0 AND 50),
    defences           text[] NOT NULL DEFAULT '{{}}',
    -- field name -> {{"page_no": n, "char_start": a, "char_end": b}}: where each value was read.
    field_sources      jsonb  NOT NULL DEFAULT '{{}}',
    extracted_by       text   NOT NULL,
    extracted_at       timestamptz NOT NULL DEFAULT now(),
    reviewed_by        text,
    reviewed_at        timestamptz,
    CONSTRAINT case_records_review_pair CHECK ((reviewed_by IS NULL) = (reviewed_at IS NULL))
);

-- ───────────── Buyer cases ─────────────

CREATE TABLE cases (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title       text NOT NULL,
    claim_type  text NOT NULL CHECK (claim_type IN ('delayed_possession', 'refund', 'other')),
    status      text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'reading', 'questions', 'report_ready')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE case_documents (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id      uuid    NOT NULL REFERENCES cases (id) ON DELETE CASCADE,
    filename     text    NOT NULL,
    kind         text    NOT NULL CHECK (kind IN ('agreement', 'allotment_letter', 'receipt', 'builder_letter', 'hearing_order', 'other')),
    sha256       char(64) NOT NULL,
    page_count   integer NOT NULL CHECK (page_count > 0),
    storage_key  text    NOT NULL,
    uploaded_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT case_documents_unique_file UNIQUE (case_id, sha256)
);

CREATE TABLE facts (
    id            bigserial PRIMARY KEY,
    case_id       uuid    NOT NULL REFERENCES cases (id) ON DELETE CASCADE,
    document_id   uuid    NOT NULL REFERENCES case_documents (id) ON DELETE CASCADE,
    key           text    NOT NULL,
    label         text    NOT NULL,
    value         text    NOT NULL,
    page_no       integer NOT NULL CHECK (page_no >= 1),
    char_start    integer NOT NULL CHECK (char_start >= 0),
    char_end      integer NOT NULL,
    quote         text    NOT NULL CHECK (char_length(quote) > 0),
    confidence    text    NOT NULL CHECK (confidence IN ('high', 'review')),
    confirmed     boolean NOT NULL DEFAULT false,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT facts_span_valid CHECK (char_end > char_start)
);
CREATE INDEX facts_case_idx ON facts (case_id);

-- A fact must point at a page that exists, in a document of the same case.
CREATE FUNCTION facts_check_source() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    doc record;
BEGIN
    SELECT case_id, page_count INTO doc FROM case_documents WHERE id = NEW.document_id;
    IF doc.case_id <> NEW.case_id THEN
        RAISE EXCEPTION 'fact source document belongs to another case' USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.page_no > doc.page_count THEN
        RAISE EXCEPTION 'fact page % is beyond the document''s % pages', NEW.page_no, doc.page_count
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER facts_check_source BEFORE INSERT OR UPDATE ON facts
    FOR EACH ROW EXECUTE FUNCTION facts_check_source();
"""

DOWNGRADE = """
DROP TABLE IF EXISTS facts;
DROP FUNCTION IF EXISTS facts_check_source();
DROP TABLE IF EXISTS case_documents;
DROP TABLE IF EXISTS cases;
DROP TABLE IF EXISTS case_records;
DROP TABLE IF EXISTS order_chunks;
DROP TABLE IF EXISTS order_pages;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS fetch_log;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
