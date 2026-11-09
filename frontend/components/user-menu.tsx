"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { logout } from "@/lib/auth-api";

function initials(name: string, email: string) {
  const parts = (name || email).trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

export default function UserMenu({ name, email }: { name: string; email: string }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const path = usePathname();

  useEffect(() => setOpen(false), [path]);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  async function signOut() {
    setBusy(true);
    try {
      await logout();
    } finally {
      window.location.assign("/");
    }
  }

  return (
    <div className="usermenu" ref={ref}>
      <button className="usermenu-trigger" aria-label={`Account menu for ${name || email}`} aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <span className="avatar" aria-hidden="true">{initials(name, email)}</span>
        <span className="usermenu-name">{name || email}</span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
      </button>
      {open && (
        <div className="usermenu-panel" role="menu">
          <div className="usermenu-who">
            <b>{name || "Your account"}</b>
            <span>{email}</span>
          </div>
          <Link role="menuitem" href="/dashboard">Your cases</Link>
          <Link role="menuitem" href="/calculator" className="usermenu-mobile">Interest calculator</Link>
          <Link role="menuitem" href="/method" className="usermenu-mobile">How it works</Link>
          <Link role="menuitem" href="/account">Account settings</Link>
          <button role="menuitem" onClick={signOut} disabled={busy}>{busy ? "Signing out…" : "Sign out"}</button>
        </div>
      )}
    </div>
  );
}
