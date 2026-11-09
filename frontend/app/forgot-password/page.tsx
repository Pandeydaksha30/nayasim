"use client";

import Link from "next/link";
import { useState } from "react";
import { TextField } from "@/components/auth-fields";
import AuthShell from "@/components/auth-shell";
import styles from "@/components/auth.module.css";
import { Banner, CheckIcon } from "@/components/icons";
import { forgotPassword } from "@/lib/auth-api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await forgotPassword(email.trim());
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send the email.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell>
      {sent ? (
        <>
          <div className={styles.iconBadge}><CheckIcon size={20} /></div>
          <h1>Check your inbox</h1>
          <p className={styles.lede}>
            If an account uses <b>{email.trim()}</b>, we&apos;ve sent it a link to choose a new password. The link
            expires in 1 hour.
          </p>
          <Link className={`btn ${styles.submit}`} href="/login">Back to sign in</Link>
          <p className={styles.fine}>Signed up with Google? Use &ldquo;Continue with Google&rdquo; instead; there is no password to reset.</p>
        </>
      ) : (
        <>
          <h1>Reset your password</h1>
          <p className={styles.lede}>Enter the email you signed up with and we&apos;ll send you a reset link.</p>
          {error && <div className={styles.notice} role="alert"><Banner tone="error">{error}</Banner></div>}
          <form className={styles.stack} onSubmit={submit}>
            <TextField label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" autoFocus />
            <button className={`btn btn-primary ${styles.submit}`} disabled={busy}>
              {busy ? "Sending…" : "Send reset link"}
            </button>
          </form>
          <div className={styles.alt}>
            Remembered it? <Link href="/login">Sign in</Link>
          </div>
        </>
      )}
    </AuthShell>
  );
}
