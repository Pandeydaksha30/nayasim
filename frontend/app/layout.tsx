import type { Metadata } from "next";
import Link from "next/link";
import { IBM_Plex_Mono, Inter, Source_Serif_4 } from "next/font/google";
import { Banner, ScaleIcon } from "@/components/icons";
import TopNav from "@/components/top-nav";
import "./globals.css";

const sans = Inter({ subsets: ["latin"], variable: "--font-sans" });
// Serif is reserved for legal documents (agreements, orders, the complaint draft).
const serif = Source_Serif_4({ subsets: ["latin"], weight: ["400", "600"], variable: "--font-serif" });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: { default: "NyayaSim", template: "%s · NyayaSim" },
  description: "See how a RERA hearing on your facts is likely to go, before you file.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${serif.variable} ${mono.variable}`}>
      <body>
        <header className="topbar">
          <div className="topbar-inner">
            <Link href="/" className="brand" aria-label="NyayaSim home">
              <span className="brand-mark"><ScaleIcon size={17} /></span>
              <span>NyayaSim</span>
            </Link>
            <TopNav />
            <div className="spacer" />
            <div className="user">
              <div className="user-text">
                <span>Ananya Mehra</span>
                <span>Homebuyer</span>
              </div>
              <span className="avatar" aria-hidden>AM</span>
            </div>
          </div>
        </header>
        <div className="demo-bar">
          <Banner tone="warn">
            <b>Demo build.</b> The case, project and every order reference marked DEMO are fictional. Money figures are
            computed live by the calculation service.
          </Banner>
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
