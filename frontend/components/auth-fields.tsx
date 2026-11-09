"use client";

/** Form pieces shared by the account pages: password field with show/hide, Google button. */
import { useId, useState } from "react";
import { googleStartUrl, passwordProblem } from "@/lib/auth-api";
import styles from "./auth.module.css";

export function PasswordField({
  label,
  value,
  onChange,
  autoComplete,
  email,
  showRules = false,
  aside,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete: "current-password" | "new-password";
  email?: string;
  showRules?: boolean;
  aside?: React.ReactNode;
}) {
  const id = useId();
  const [shown, setShown] = useState(false);
  const problem = showRules && value ? passwordProblem(value, email) : null;
  return (
    <div className="field">
      <div className={styles.labelRow}>
        <label className="field-label" htmlFor={id}>{label}</label>
        {aside}
      </div>
      <div className={styles.pwWrap}>
        <input
          id={id}
          className={styles.control}
          type={shown ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete={autoComplete}
          required
          maxLength={128}
          aria-invalid={problem ? true : undefined}
          aria-describedby={showRules ? `${id}-hint` : undefined}
        />
        <button type="button" className={styles.reveal} onClick={() => setShown((s) => !s)} aria-pressed={shown}>
          {shown ? "Hide" : "Show"}
        </button>
      </div>
      {showRules && (
        <div id={`${id}-hint`} className={`${styles.hint} ${problem ? styles.hintBad : value ? styles.hintOk : ""}`}>
          {problem ?? (value ? "Looks good." : "At least 10 characters. A short phrase is easy to remember and hard to guess.")}
        </div>
      )}
    </div>
  );
}

export function TextField({
  label,
  type = "text",
  value,
  onChange,
  autoComplete,
  autoFocus,
}: {
  label: string;
  type?: "text" | "email";
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
  autoFocus?: boolean;
}) {
  const id = useId();
  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>{label}</label>
      <input
        id={id}
        className={styles.control}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        autoFocus={autoFocus}
        required
        maxLength={type === "email" ? 254 : 120}
        spellCheck={false}
      />
    </div>
  );
}

/** Google's standard "G" mark, as its sign-in branding guidelines ask for. */
function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  );
}

export function GoogleButton({ next, label = "Continue with Google" }: { next?: string; label?: string }) {
  // A plain link: the browser goes to Google and comes back to our callback (no Google script runs here).
  return (
    <a className={`btn ${styles.google}`} href={googleStartUrl(next)}>
      <GoogleMark /> {label}
    </a>
  );
}
