import type { Metadata } from "next";
import { redirect } from "next/navigation";
import AuthShell from "@/components/auth-shell";
import { safeNext } from "@/lib/auth-api";
import { googleEnabled } from "@/lib/auth-config";
import { getUser } from "@/lib/server-session";
import LoginForm from "./login-form";

export const metadata: Metadata = { title: "Sign in" };
export const dynamic = "force-dynamic";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; error?: string; reset?: string }>;
}) {
  const sp = await searchParams;
  const next = safeNext(sp.next);
  if (await getUser()) redirect(next);
  return (
    <AuthShell>
      <LoginForm next={next} google={await googleEnabled()} error={sp.error ?? null} reset={sp.reset === "1"} />
    </AuthShell>
  );
}
