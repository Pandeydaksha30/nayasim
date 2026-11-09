import type { Metadata } from "next";
import Link from "next/link";
import { IBM_Plex_Mono, Inter, Source_Serif_4 } from "next/font/google";
import EarlyAccessNotice from "@/components/early-access-notice";
import { ScaleIcon } from "@/components/icons";
import TopNav from "@/components/top-nav";
import UserMenu from "@/components/user-menu";
import { getUser } from "@/lib/server-session";
import "./globals.css";

const sans = Inter({ subsets: ["latin"], variable: "--font-sans" });
// Serif is reserved for legal documents (agreements, orders, the complaint draft) and headings
// on the public pages.
const serif = Source_Serif_4({ subsets: ["latin"], weight: ["400", "600"], variable: "--font-serif" });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: { default: "NyayaSim — RERA dispute preparation", template: "%s · NyayaSim" },
  description: "See how a RERA hearing on your facts is likely to go, before you file.",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const user = await getUser();
  return (
    <html lang="en" className={`${sans.variable} ${serif.variable} ${mono.variable}`}>
      <body>
        <a href="#content" className="skip-link">Skip to content</a>
        <header className="topbar">
          <div className="topbar-inner">
            <Link href={user ? "/dashboard" : "/"} className="brand" aria-label="NyayaSim home">
              <span className="brand-mark"><ScaleIcon size={17} /></span>
              <span>NyayaSim</span>
            </Link>
            <TopNav signedIn={!!user} />
            <div className="spacer" />
            {user ? (
              <UserMenu name={user.name} email={user.email} />
            ) : (
              <div className="topbar-actions">
                <Link href="/login" className="btn btn-quiet">Sign in</Link>
                <Link href="/signup" className="btn btn-primary">Create account</Link>
              </div>
            )}
          </div>
        </header>
        <EarlyAccessNotice />
        <div id="content">{children}</div>
        <footer className="footer">
          <div className="footer-inner">
            <p>
              NyayaSim gives decision support and drafting help. It is not legal advice and does not replace an advocate.
              Predictions come from past orders and can be wrong.
            </p>
            <nav aria-label="Legal">
              <Link href="/method">How it works</Link>
              <Link href="/privacy">Privacy</Link>
              <Link href="/terms">Terms</Link>
            </nav>
          </div>
        </footer>
      </body>
    </html>
  );
}
