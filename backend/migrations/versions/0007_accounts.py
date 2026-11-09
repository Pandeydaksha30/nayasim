"""User accounts: email + password and Google sign-in, sessions, one-time email tokens, an
audit log, and an owner on every buyer case.

Revision ID: 0007
Create date: 2026-11-09

- users: email is stored lowercased and unique. password_hash is NULL for Google-only accounts;
  google_sub is NULL for password-only accounts. failed_logins/locked_until drive lockout.
- user_sessions: the browser holds a random token in an httpOnly cookie; only its SHA-256 is
  stored here, so a database leak does not give working sessions.
- auth_tokens: email verification and password reset links. Hashed, single use, expiring.
- auth_events: sign-ins, failures, password changes, deletions (who, when, from where) for the
  access log the DPDP Act expects.
- cases.user_id: the owner. Existing cases keep NULL; only shared demo cases (is_demo) without an
  owner are visible to every signed-in user. Deleting a user deletes their cases.
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE users (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            email           text NOT NULL,
            name            text NOT NULL DEFAULT '',
            password_hash   text,
            google_sub      text UNIQUE,
            email_verified  boolean NOT NULL DEFAULT false,
            failed_logins   integer NOT NULL DEFAULT 0,
            locked_until    timestamptz,
            created_at      timestamptz NOT NULL DEFAULT now(),
            last_login_at   timestamptz,
            CONSTRAINT users_email_lower CHECK (email = lower(email)),
            CONSTRAINT users_has_login CHECK (password_hash IS NOT NULL OR google_sub IS NOT NULL)
        );
        CREATE UNIQUE INDEX users_email_key ON users (email);

        CREATE TABLE user_sessions (
            token_hash   text PRIMARY KEY,
            user_id      uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            created_at   timestamptz NOT NULL DEFAULT now(),
            expires_at   timestamptz NOT NULL,
            last_seen_at timestamptz NOT NULL DEFAULT now(),
            ip           text,
            user_agent   text
        );
        CREATE INDEX user_sessions_user_idx ON user_sessions (user_id);

        CREATE TABLE auth_tokens (
            token_hash  text PRIMARY KEY,
            user_id     uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            purpose     text NOT NULL CHECK (purpose IN ('verify_email', 'reset_password')),
            created_at  timestamptz NOT NULL DEFAULT now(),
            expires_at  timestamptz NOT NULL,
            used_at     timestamptz
        );
        CREATE INDEX auth_tokens_user_idx ON auth_tokens (user_id, purpose);

        CREATE TABLE auth_events (
            id          bigserial PRIMARY KEY,
            user_id     uuid REFERENCES users (id) ON DELETE SET NULL,
            email       text,
            event       text NOT NULL,
            ip          text,
            user_agent  text,
            at          timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX auth_events_user_idx ON auth_events (user_id, at DESC);

        ALTER TABLE cases ADD COLUMN user_id uuid REFERENCES users (id) ON DELETE CASCADE;
        CREATE INDEX cases_user_idx ON cases (user_id, created_at DESC);
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE cases DROP COLUMN IF EXISTS user_id;
        DROP TABLE IF EXISTS auth_events;
        DROP TABLE IF EXISTS auth_tokens;
        DROP TABLE IF EXISTS user_sessions;
        DROP TABLE IF EXISTS users;
    """)
