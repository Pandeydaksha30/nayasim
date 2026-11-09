import type { Metadata } from "next";
import LegalDoc from "@/components/legal-doc";

export const metadata: Metadata = { title: "Privacy Policy" };

export default function PrivacyPage() {
  return (
    <LegalDoc title="Privacy Policy" updated="9 November 2026">
      <p>
        This policy explains what NyayaSim collects when you use it, why, and what you can do about it. It is written
        with the Digital Personal Data Protection Act, 2023 in mind.
      </p>

      <h2>What we collect</h2>
      <ul>
        <li><b>Account details:</b> your name and email address. If you set a password, we keep only a one-way hash of it (Argon2id), never the password itself. If you sign in with Google, we receive your Google account ID, name and email address, and nothing else.</li>
        <li><b>Your case material:</b> documents you upload, the text read from them, facts extracted from them, your answers to follow-up questions, and the reports produced.</li>
        <li><b>Security records:</b> when you sign in, sign out, reset your password or delete your account, we record the time, your IP address and your browser&apos;s user-agent string.</li>
      </ul>
      <p>We do not use advertising or analytics trackers, and we do not sell or rent personal data.</p>

      <h2>Why we use it</h2>
      <ul>
        <li>To run your account and keep it secure, including detecting repeated failed sign-ins.</li>
        <li>To read your documents and prepare your case analysis, which is the service you ask us for.</li>
        <li>To send you account emails: confirming your address and resetting your password. We do not send marketing email.</li>
      </ul>

      <h2>Who else sees it</h2>
      <ul>
        <li><b>Nobody else sees your cases.</b> Each case is visible only to the account that created it.</li>
        <li><b>AI models:</b> real documents are not sent to any outside AI service unless that service has agreed not to keep or train on the data. Until such a service is in place, only documents you mark as fictional demo documents are sent to one.</li>
        <li><b>Google</b>, only if you choose &ldquo;Continue with Google&rdquo;, to confirm who you are.</li>
        <li><b>Our hosting and email providers</b>, who store and deliver data on our behalf.</li>
        <li>Authorities, where the law requires it.</li>
      </ul>

      <h2>How long we keep it</h2>
      <p>
        We keep your account and cases until you delete them. Deleting your account permanently removes your account,
        every case, uploaded document, extracted fact and report. Security records of sign-in events are kept for up
        to one year, so that misuse can be investigated, and are then deleted.
      </p>

      <h2>Your rights</h2>
      <p>
        You can see and correct your profile in Account settings, and delete your account and all its data there at any
        time. You can also ask us for a summary of the personal data we hold about you, or raise a grievance, by writing to
        the contact below. If you are not satisfied with our answer, you may complain to the Data Protection Board of India.
      </p>

      <h2>Security</h2>
      <p>
        Connections are encrypted with HTTPS. Sessions use secure, http-only cookies that page scripts cannot read.
        Passwords are hashed with Argon2id, sign-in attempts are rate-limited, and accounts lock for 15 minutes after
        repeated wrong passwords. No system is perfectly secure; if we learn of a breach affecting your data, we will
        tell you and the Board as the law requires.
      </p>

      <h2>Contact</h2>
      <p>Grievance contact: to be published before public launch.</p>
    </LegalDoc>
  );
}
