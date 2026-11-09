import type { Metadata } from "next";
import AuthShell from "@/components/auth-shell";
import ResetForm from "./reset-form";

export const metadata: Metadata = { title: "Choose a new password" };

export default async function ResetPasswordPage({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  return (
    <AuthShell>
      <ResetForm token={(await searchParams).token ?? ""} />
    </AuthShell>
  );
}
