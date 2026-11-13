import { requireUser } from "@/lib/server-session";
import SearchClient from "./search-client";

export const metadata = { title: "Search past orders" };

export default async function SearchPage() {
  await requireUser("/search");
  return (
    <main className="page" style={{ maxWidth: 1080 }}>
      <h1>Search past orders</h1>
      <p className="muted" style={{ margin: "8px 0 20px", maxWidth: "72ch" }}>
        Searches the text of public orders of the Haryana Real Estate Regulatory Authority, Gurugram, stored on this
        server. Your words are matched on this server only; nothing is sent to an outside service. Each result shows
        the order, the page and the exact passage.
      </p>
      <SearchClient />
    </main>
  );
}
