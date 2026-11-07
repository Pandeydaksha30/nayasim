"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Cases", match: (p: string) => p === "/" || p.startsWith("/cases") },
  { href: "/calculator", label: "Interest calculator", match: (p: string) => p.startsWith("/calculator") },
  { href: "/method", label: "How it works", match: (p: string) => p.startsWith("/method") },
];

export default function TopNav() {
  const path = usePathname();
  return (
    <nav className="topnav" aria-label="Main">
      {LINKS.map((l) => (
        <Link key={l.href} href={l.href} aria-current={l.match(path) ? "page" : undefined}>
          {l.label}
        </Link>
      ))}
    </nav>
  );
}
