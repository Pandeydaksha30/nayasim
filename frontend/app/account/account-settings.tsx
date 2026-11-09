"use client";

import { useState } from "react";
import { PasswordField } from "@/components/auth-fields";
import {
  changePassword,
  deleteAccount,
  logoutAll,
  passwordProblem,
  updateProfile,
  type User,
} from "@/lib/auth-api";
import { fmtDate } from "@/lib/format";
import styles from "./account.module.css";

type Msg = { ok: boolean; text: string } | null;
const show = (m: Msg) => m && <span className={m.ok ? styles.msgOk : styles.msgBad} role={m.ok ? "status" : "alert"}>{m.text}</span>;
const errText = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong.");

export default function AccountSettings({ user }: { user: User }) {
  return (
    <div>
      <Profile user={user} />
      <SignIn user={user} />
      <Sessions />
      <Danger user={user} />
    </div>
  );
}

function Profile({ user }: { user: User }) {
  const [name, setName] = useState(user.name);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      await updateProfile(name.trim());
      setMsg({ ok: true, text: "Saved." });
    } catch (err) {
      setMsg({ ok: false, text: errText(err) });
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className={styles.section}>
      <div className={styles.intro}>
        <h2>Profile</h2>
        <p>Member since {fmtDate(user.created_at.slice(0, 10))}.</p>
      </div>
      <form className={`panel ${styles.card}`} onSubmit={save}>
        <label className="field">
          <span className="field-label">Full name</span>
          <input className={styles.control} value={name} onChange={(e) => setName(e.target.value)} maxLength={120} required autoComplete="name" />
        </label>
        <label className="field">
          <span className="field-label">Email</span>
          <input className={styles.control} value={user.email} readOnly />
          <span className="field-help">
            {user.email_verified ? "Confirmed." : "Not confirmed yet."} Email changes are not available yet.
          </span>
        </label>
        <div className={styles.actions}>
          <button className="btn btn-primary" disabled={busy || !name.trim() || name.trim() === user.name}>
            {busy ? "Saving…" : "Save changes"}
          </button>
          {show(msg)}
        </div>
      </form>
    </section>
  );
}

function SignIn({ user }: { user: User }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  const [hasPassword, setHasPassword] = useState(user.has_password);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const problem = passwordProblem(next, user.email);
    if (problem) return setMsg({ ok: false, text: problem });
    setBusy(true);
    setMsg(null);
    try {
      const r = await changePassword(hasPassword ? current : null, next);
      setMsg({ ok: true, text: r.message });
      setHasPassword(true);
      setCurrent("");
      setNext("");
    } catch (err) {
      setMsg({ ok: false, text: errText(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={styles.section}>
      <div className={styles.intro}>
        <h2>Sign-in methods</h2>
        <p>Changing your password signs you out on your other devices.</p>
      </div>
      <div className={`panel ${styles.card}`}>
        <div className={styles.row}>
          <div className={styles.rowText}>
            <b>Google</b>
            <span>{user.google_linked ? `Linked. You can sign in with ${user.email}.` : "Not linked. Sign in with Google once using this email to link it."}</span>
          </div>
          <span className={`tag ${user.google_linked ? "tag-pos" : "tag-neutral"}`}>{user.google_linked ? "Linked" : "Not linked"}</span>
        </div>
        <div className={styles.divider} />
        <form className={styles.card} style={{ padding: 0 }} onSubmit={save}>
          <div className={styles.rowText}>
            <b>{hasPassword ? "Change password" : "Set a password"}</b>
            <span>{hasPassword ? "Enter your current password, then the new one." : "Add a password so you can also sign in with your email."}</span>
          </div>
          {hasPassword && <PasswordField label="Current password" value={current} onChange={setCurrent} autoComplete="current-password" />}
          <PasswordField label="New password" value={next} onChange={setNext} autoComplete="new-password" email={user.email} showRules />
          <div className={styles.actions}>
            <button className="btn btn-primary" disabled={busy || !next || (hasPassword && !current)}>
              {busy ? "Saving…" : hasPassword ? "Update password" : "Set password"}
            </button>
            {show(msg)}
          </div>
        </form>
      </div>
    </section>
  );
}

function Sessions() {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  async function run() {
    setBusy(true);
    try {
      await logoutAll();
      window.location.assign("/login");
    } catch (err) {
      setMsg({ ok: false, text: errText(err) });
      setBusy(false);
    }
  }
  return (
    <section className={styles.section}>
      <div className={styles.intro}>
        <h2>Devices</h2>
        <p>Sessions last 30 days, then you sign in again.</p>
      </div>
      <div className={`panel ${styles.card}`}>
        <div className={styles.row}>
          <div className={styles.rowText}>
            <b>Sign out everywhere</b>
            <span>Ends every session, including this one. Use it if you signed in on a shared computer.</span>
          </div>
          <button className="btn" onClick={run} disabled={busy}>{busy ? "Signing out…" : "Sign out of all devices"}</button>
        </div>
        {show(msg)}
      </div>
    </section>
  );
}

function Danger({ user }: { user: User }) {
  const [confirm, setConfirm] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  async function run(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      await deleteAccount(user.has_password ? password : null, confirm);
      window.location.assign("/?deleted=1");
    } catch (err) {
      setMsg({ ok: false, text: errText(err) });
      setBusy(false);
    }
  }
  return (
    <section className={styles.section}>
      <div className={styles.intro}>
        <h2>Delete account</h2>
        <p>Permanently removes your account, every case, uploaded document, extracted fact and report. This cannot be undone.</p>
      </div>
      <form className={`panel ${styles.card} ${styles.danger}`} onSubmit={run}>
        <label className="field">
          <span className="field-label">Type DELETE to confirm</span>
          <input className={styles.control} value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="off" spellCheck={false} />
        </label>
        {user.has_password && <PasswordField label="Your password" value={password} onChange={setPassword} autoComplete="current-password" />}
        <div className={styles.actions}>
          <button
            className={`btn ${styles.dangerBtn}`}
            disabled={busy || confirm.trim().toUpperCase() !== "DELETE" || (user.has_password && !password)}
          >
            {busy ? "Deleting…" : "Delete my account"}
          </button>
          {show(msg)}
        </div>
      </form>
    </section>
  );
}
