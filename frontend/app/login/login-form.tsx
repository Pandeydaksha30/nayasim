"use client";

import Link from "next/link";
import { useState } from "react";
import { GoogleButton, PasswordField, TextField } from "@/components/auth-fields";
import styles from "@/components/auth.module.css";
import { Banner } from "@/components/icons";
import { ApiError } from "@/lib/api";
import { login, resendVerification } from "@/lib/auth-api";

export default function LoginForm({
  next,
  google,
  error: initialError,
  reset,
}: {
  next: string;
  google: boolean;
  error: string | null;
  reset: boolean;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(initialError);
  const [unverified, setUnverified] = useState(false);
  const [info, setInfo] = useState<string | null>(reset ? "Your password has been changed. Sign in with the new one." : null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setInfo(null);
    setUnverified(false);
    try {
      await login(email, password);
      // Full navigation so the header and every server component re-read the new session.
      window.location.assign(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed.");
      setUnverified(err instanceof ApiError && err.status === 403);
      setBusy(false);
    }
  }

  async function resend() {
    try {
      setInfo((await resendVerification(email)).message);
      setError(null);
      setUnverified(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send the email.");
    }
  }

  return (
    <>
      <h1>Sign in to NyayaSim</h1>
      <p className={styles.lede}>Pick up your cases where you left them.</p>

      {error && (
        <div className={styles.notice} role="alert">
          <Banner tone="error">
            {error}{" "}
            {unverified && (
              <button type="button" className={styles.linkBtn} onClick={resend}>
                Send a new link
              </button>
            )}
          </Banner>
        </div>
      )}
      {info && <div className={styles.notice} role="status"><Banner tone="ok">{info}</Banner></div>}

      <form className={styles.stack} onSubmit={submit} noValidate={false}>
        <TextField label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" autoFocus />
        <PasswordField
          label="Password"
          value={password}
          onChange={setPassword}
          autoComplete="current-password"
          aside={<Link href="/forgot-password">Forgot password?</Link>}
        />
        <button className={`btn btn-primary ${styles.submit}`} disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>

      {google && (
        <>
          <div className={styles.divider}>or</div>
          <GoogleButton next={next} />
        </>
      )}

      <div className={styles.alt}>
        New to NyayaSim? <Link href={`/signup${next !== "/dashboard" ? `?next=${encodeURIComponent(next)}` : ""}`}>Create an account</Link>
      </div>
    </>
  );
}
