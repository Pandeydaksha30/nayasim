"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const SIGNED_IN = [
  { href: "/dashboard", label: "Cases", match: (p: string) => p.startsWith("/dashboard") || (p.startsWith("/cases") && !p.startsWith("/cases/demo")) },
  { href: "/search", label: "Search orders", match: (p: string) => p.startsWith("/search") },
  { href: "/calculator", label: "Interest calculator", match: (p: string) => p.startsWith("/calculator") },
  { href: "/method", label: "How it works", match: (p: string) => p.startsWith("/method") },
];
const SIGNED_OUT = [
  { href: "/method", label: "How it works", match: (p: string) => p.startsWith("/method") },
  { href: "/cases/demo/report", label: "Example report", match: (p: string) => p.startsWith("/cases/demo") },
  { href: "/calculator", label: "Interest calculator", match: (p: string) => p.startsWith("/calculator") },
];

export default function TopNav({ signedIn }: { signedIn: boolean }) {
  const path = usePathname();
  return (
    <nav className="topnav" aria-label="Main">
      {(signedIn ? SIGNED_IN : SIGNED_OUT).map((l) => (
        <Link key={l.href} href={l.href} aria-current={l.match(path) ? "page" : undefined}>
          {l.label}
        </Link>
      ))}
    </nav>
  );
}
