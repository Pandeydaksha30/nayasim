"""Buyer document pages, follow-up answers, demo flag; facts must quote the stored page.

Revision ID: 0003
Create date: 2026-11-07

* case_document_pages: text of every page of a buyer's upload (text layer or OCR).
* case_answers: the buyer's answers to follow-up questions.
* cases.is_demo: fictional demo cases. Only these may be sent to a model that may retain
  data (the free Gemini tier); real buyer documents need a no-retention model.
* facts: the trigger now also requires the quote to be exactly the stored page text at
  [char_start, char_end), whenever that page's text is stored.
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

UPGRADE = """
ALTER TABLE cases ADD COLUMN is_demo boolean NOT NULL DEFAULT false;

CREATE TABLE case_document_pages (
    document_id     uuid    NOT NULL REFERENCES case_documents (id) ON DELETE CASCADE,
    page_no         integer NOT NULL CHECK (page_no >= 1),
    text            text    NOT NULL,
    text_source     text    NOT NULL CHECK (text_source IN ('text_layer', 'ocr')),
    ocr_engine      text,
    ocr_confidence  numeric(5, 2) CHECK (ocr_confidence BETWEEN 0 AND 100),
    PRIMARY KEY (document_id, page_no),
    CONSTRAINT case_document_pages_ocr_named CHECK (text_source = 'text_layer' OR ocr_engine IS NOT NULL)
);

CREATE TABLE case_answers (
    case_id      uuid NOT NULL REFERENCES cases (id) ON DELETE CASCADE,
    question_id  text NOT NULL,
    answer       text NOT NULL CHECK (char_length(answer) > 0),
    answered_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (case_id, question_id)
);

CREATE OR REPLACE FUNCTION facts_check_source() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    doc record;
    page_text text;
BEGIN
    SELECT case_id, page_count INTO doc FROM case_documents WHERE id = NEW.document_id;
    IF doc.case_id <> NEW.case_id THEN
        RAISE EXCEPTION 'fact source document belongs to another case' USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.page_no > doc.page_count THEN
        RAISE EXCEPTION 'fact page % is beyond the document''s % pages', NEW.page_no, doc.page_count
            USING ERRCODE = 'check_violation';
    END IF;
    SELECT text INTO page_text FROM case_document_pages
        WHERE document_id = NEW.document_id AND page_no = NEW.page_no;
    IF page_text IS NOT NULL
       AND substr(page_text, NEW.char_start + 1, NEW.char_end - NEW.char_start) IS DISTINCT FROM NEW.quote THEN
        RAISE EXCEPTION 'fact quote does not match the stored page text at that position'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;
"""

DOWNGRADE = """
CREATE OR REPLACE FUNCTION facts_check_source() RETURNS trigger LANGUAGE plpgsql AS $$
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
DROP TABLE IF EXISTS case_answers;
DROP TABLE IF EXISTS case_document_pages;
ALTER TABLE cases DROP COLUMN IF EXISTS is_demo;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
