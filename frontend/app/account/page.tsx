import type { Metadata } from "next";
import { requireUser } from "@/lib/server-session";
import AccountSettings from "./account-settings";

export const metadata: Metadata = { title: "Account settings" };
export const dynamic = "force-dynamic";

export default async function AccountPage() {
  const user = await requireUser("/account");
  return (
    <main className="page page-narrow">
      <div className="page-head">
        <div>
          <h1>Account settings</h1>
          <p>Your profile, how you sign in, and your data.</p>
        </div>
      </div>
      <AccountSettings user={user} />
    </main>
  );
}
