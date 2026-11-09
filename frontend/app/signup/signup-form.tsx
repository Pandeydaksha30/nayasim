"use client";

import Link from "next/link";
import { useState } from "react";
import { GoogleButton, PasswordField, TextField } from "@/components/auth-fields";
import styles from "@/components/auth.module.css";
import { Banner, CheckIcon } from "@/components/icons";
import { passwordProblem, resendVerification, signup } from "@/lib/auth-api";

export default function SignupForm({ next, google }: { next: string; google: boolean }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [terms, setTerms] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [resent, setResent] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const problem = passwordProblem(password, email);
    if (problem) return setError(problem);
    if (!terms) return setError("Please accept the Terms and Privacy Policy to continue.");
    setBusy(true);
    setError(null);
    try {
      await signup(name.trim(), email.trim(), password, terms);
      setSentTo(email.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the account.");
    } finally {
      setBusy(false);
    }
  }

  if (sentTo) {
    return (
      <>
        <div className={styles.iconBadge}><CheckIcon size={20} /></div>
        <h1>Check your inbox</h1>
        <p className={styles.lede}>
          We sent a confirmation link to <b>{sentTo}</b>. Open it to finish setting up your account. The link
          works once and expires in 24 hours.
        </p>
        {resent && <div className={styles.notice}><Banner tone="ok">{resent}</Banner></div>}
        <div className={styles.fine}>
          Nothing arrived after a few minutes? Check your spam folder, or{" "}
          <button
            type="button"
            className={styles.linkBtn}
            onClick={async () => {
              try {
                setResent((await resendVerification(sentTo)).message);
              } catch (err) {
                setResent(err instanceof Error ? err.message : "Could not send the email.");
              }
            }}
          >
            send the link again
          </button>
          .
        </div>
        <div className={styles.alt}>
          Confirmed already? <Link href={`/login?next=${encodeURIComponent(next)}`}>Sign in</Link>
        </div>
      </>
    );
  }

  return (
    <>
      <h1>Create your account</h1>
      <p className={styles.lede}>Upload your papers, check the facts and see how a hearing could go. Free while in early access.</p>

      {error && <div className={styles.notice} role="alert"><Banner tone="error">{error}</Banner></div>}

      {google && (
        <>
          <GoogleButton next={next} label="Sign up with Google" />
          <div className={styles.divider}>or with email</div>
        </>
      )}

      <form className={styles.stack} onSubmit={submit}>
        <TextField label="Full name" value={name} onChange={setName} autoComplete="name" autoFocus={!google} />
        <TextField label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" />
        <PasswordField label="Password" value={password} onChange={setPassword} autoComplete="new-password" email={email} showRules />
        <label className={styles.check}>
          <input type="checkbox" checked={terms} onChange={(e) => setTerms(e.target.checked)} />
          <span>
            I agree to the <Link href="/terms" target="_blank">Terms of Use</Link> and{" "}
            <Link href="/privacy" target="_blank">Privacy Policy</Link>, and understand NyayaSim is not legal advice.
          </span>
        </label>
        <button className={`btn btn-primary ${styles.submit}`} disabled={busy}>
          {busy ? "Creating account…" : "Create account"}
        </button>
      </form>

      <div className={styles.alt}>
        Already have an account? <Link href={`/login${next !== "/dashboard" ? `?next=${encodeURIComponent(next)}` : ""}`}>Sign in</Link>
      </div>
    </>
  );
}
