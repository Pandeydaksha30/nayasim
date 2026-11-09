"use client";

import Link from "next/link";
import { useState } from "react";
import { PasswordField } from "@/components/auth-fields";
import styles from "@/components/auth.module.css";
import { Banner } from "@/components/icons";
import { passwordProblem, resetPassword } from "@/lib/auth-api";

export default function ResetForm({ token }: { token: string }) {
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(token ? null : "This link is incomplete. Open the link from the email again.");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const problem = passwordProblem(pw);
    if (problem) return setError(problem);
    if (pw !== pw2) return setError("The two passwords don't match.");
    setBusy(true);
    setError(null);
    try {
      await resetPassword(token, pw);
      window.location.assign("/login?reset=1");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change the password.");
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Choose a new password</h1>
      <p className={styles.lede}>After this, you&apos;ll be signed out on every device and can sign in with the new password.</p>
      {error && <div className={styles.notice} role="alert"><Banner tone="error">{error} {error.includes("expired") && <Link href="/forgot-password">Get a new link</Link>}</Banner></div>}
      <form className={styles.stack} onSubmit={submit}>
        <PasswordField label="New password" value={pw} onChange={setPw} autoComplete="new-password" showRules />
        <PasswordField label="Repeat new password" value={pw2} onChange={setPw2} autoComplete="new-password" />
        <button className={`btn btn-primary ${styles.submit}`} disabled={busy || !token}>
          {busy ? "Saving…" : "Save new password"}
        </button>
      </form>
    </>
  );
}
