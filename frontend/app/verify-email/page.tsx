import type { Metadata } from "next";
import AuthShell from "@/components/auth-shell";
import VerifyEmail from "./verify-email";

export const metadata: Metadata = { title: "Confirm your email" };

export default async function VerifyEmailPage({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  return (
    <AuthShell>
      <VerifyEmail token={(await searchParams).token ?? ""} />
    </AuthShell>
  );
}
