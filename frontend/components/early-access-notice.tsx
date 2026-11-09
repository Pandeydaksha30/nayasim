"use client";

/** The "early version" notice, shown inside the product, not on the landing or sign-in pages. */
import { usePathname } from "next/navigation";
import { Banner } from "./icons";

const HIDDEN = ["/", "/login", "/signup", "/forgot-password", "/reset-password", "/verify-email", "/terms", "/privacy"];

export default function EarlyAccessNotice() {
  const path = usePathname();
  if (HIDDEN.includes(path)) return null;
  return (
    <div className="demo-bar">
      <Banner tone="warn">
        <b>Early version.</b> The example case and anything marked DEMO are fictional. Reports show patterns in past
        orders; they are not legal advice.
      </Banner>
    </div>
  );
}
