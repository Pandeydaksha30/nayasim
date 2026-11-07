import type { Metadata } from "next";
import Link from "next/link";
import { IBM_Plex_Mono, IBM_Plex_Sans, Source_Serif_4 } from "next/font/google";
import "./globals.css";

const serif = Source_Serif_4({ subsets: ["latin"], weight: ["400", "600"], variable: "--font-serif" });
const sans = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-sans" });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: { default: "NyayaSim", template: "%s · NyayaSim" },
  description: "See how a RERA hearing on your facts is likely to go, before you file.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${serif.variable} ${sans.variable} ${mono.variable}`}>
      <body>
        <header className="topbar">
          <div className="topbar-inner">
            <Link href="/" className="wordmark">
              Nyaya<span>Sim</span>
            </Link>
            <nav className="topnav" aria-label="Main">
              <Link href="/">Cases</Link>
              <Link href="/calculator">Interest calculator</Link>
              <Link href="/method">How it works</Link>
            </nav>
            <div className="spacer" />
            <span className="account">A. Mehra</span>
          </div>
        </header>
        <div className="demo-strip" role="note">
          <div>Demo build. The case, project and every order reference marked DEMO are fictional.</div>
        </div>
        {children}
        <footer className="footer">
          <div>
            NyayaSim gives decision support and drafting help. It is not legal advice and does not replace an advocate.
            Predictions come from past orders and can be wrong.
          </div>
        </footer>
      </body>
    </html>
  );
}
