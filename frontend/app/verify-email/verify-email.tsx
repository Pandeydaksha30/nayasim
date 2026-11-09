"use client";

import Link from "next/link";
import { useState } from "react";
import styles from "@/components/auth.module.css";
import { CheckIcon, ErrorIcon } from "@/components/icons";
import { verifyEmail } from "@/lib/auth-api";

/**
 * The link only lands here; confirming takes a click. (Some email scanners open every link in
 * a message; requiring a click stops them from using up the one-time link.)
 */
export default function VerifyEmail({ token }: { token: string }) {
  const [state, setState] = useState<"ready" | "busy" | "done" | "failed">(token ? "ready" : "failed");
  const [error, setError] = useState(token ? "" : "This link is incomplete. Open the link from the email again.");

  async function confirm() {
    setState("busy");
    try {
      await verifyEmail(token);
      setState("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not confirm your email.");
      setState("failed");
    }
  }

  if (state === "done") {
    return (
      <>
        <div className={`${styles.iconBadge} ${styles.iconBadgeOk}`}><CheckIcon size={20} /></div>
        <h1>Email confirmed</h1>
        <p className={styles.lede}>Your account is ready and you are signed in.</p>
        <a className={`btn btn-primary ${styles.submit}`} href="/dashboard">Go to your cases</a>
      </>
    );
  }
  if (state === "failed") {
    return (
      <>
        <div className={`${styles.iconBadge} ${styles.iconBadgeBad}`}><ErrorIcon size={20} /></div>
        <h1>This link didn&apos;t work</h1>
        <p className={styles.lede}>{error}</p>
        <Link className={`btn ${styles.submit}`} href="/login">Back to sign in</Link>
        <p className={styles.fine}>On the sign-in page, enter your email and password to get a new confirmation link.</p>
      </>
    );
  }
  return (
    <>
      <div className={styles.iconBadge}><CheckIcon size={20} /></div>
      <h1>Confirm your email</h1>
      <p className={styles.lede}>One click and your NyayaSim account is ready.</p>
      <button className={`btn btn-primary ${styles.submit}`} onClick={confirm} disabled={state === "busy"}>
        {state === "busy" ? "Confirming…" : "Confirm email address"}
      </button>
    </>
  );
}
