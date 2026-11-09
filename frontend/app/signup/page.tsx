import type { Metadata } from "next";
import { redirect } from "next/navigation";
import AuthShell from "@/components/auth-shell";
import { safeNext } from "@/lib/auth-api";
import { googleEnabled } from "@/lib/auth-config";
import { getUser } from "@/lib/server-session";
import SignupForm from "./signup-form";

export const metadata: Metadata = { title: "Create your account" };
export const dynamic = "force-dynamic";

export default async function SignupPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const next = safeNext((await searchParams).next);
  if (await getUser()) redirect(next);
  return (
    <AuthShell>
      <SignupForm next={next} google={await googleEnabled()} />
    </AuthShell>
  );
}
