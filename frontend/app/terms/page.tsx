import type { Metadata } from "next";
import Link from "next/link";
import LegalDoc from "@/components/legal-doc";

export const metadata: Metadata = { title: "Terms of Use" };

export default function TermsPage() {
  return (
    <LegalDoc title="Terms of Use" updated="9 November 2026">
      <p>These terms apply when you create an account on NyayaSim or use the site.</p>

      <h2>1. What NyayaSim is</h2>
      <p>
        NyayaSim is a decision-support tool for people preparing a complaint before a Real Estate Regulatory Authority.
        It reads documents you provide, calculates amounts using the rules you can see, and describes how similar past
        orders were decided. <b>It is not legal advice</b>, it is not a law firm, and using it does not create an
        advocate–client relationship. Before you file, take advice from an advocate.
      </p>

      <h2>2. Predictions and figures</h2>
      <p>
        Outcome shares and simulated hearings describe patterns in past public orders. They can be wrong, and the
        authority deciding your case is not bound by them. Interest and refund figures depend on the documents and
        answers you give and on the rate you confirm. Check every figure before relying on it.
      </p>

      <h2>3. Your account</h2>
      <ul>
        <li>Give your real name and an email address you control. You must be at least 18 years old.</li>
        <li>Keep your password private. You are responsible for what is done through your account.</li>
        <li>Tell us promptly if you think someone else has used your account.</li>
      </ul>

      <h2>4. Your documents</h2>
      <p>
        Upload only documents you are entitled to share. You keep all rights in them. You allow us to store and process
        them only to provide the service to you, as described in the <Link href="/privacy">Privacy Policy</Link>. Mark
        documents as demo documents only if they are fictional.
      </p>

      <h2>5. Acceptable use</h2>
      <p>
        Do not try to access other users&apos; data, probe or overload the service, get around rate limits or security
        controls, or use NyayaSim to harass anyone or file knowingly false complaints.
      </p>

      <h2>6. Early access</h2>
      <p>
        NyayaSim is in early access and is provided free of charge, as it is. Features may change or be removed, and the
        service may be unavailable at times. To the extent the law allows, we are not liable for losses arising from
        reliance on its output.
      </p>

      <h2>7. Ending your account</h2>
      <p>
        You can delete your account at any time in Account settings; your data is deleted with it. We may suspend
        accounts that break these terms.
      </p>

      <h2>8. Law</h2>
      <p>These terms are governed by the laws of India.</p>
    </LegalDoc>
  );
}
