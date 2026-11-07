import { notFound } from "next/navigation";
import { getCase } from "@/lib/demo-case";
import FactsView from "./facts-view";

export const metadata = { title: "Facts" };

export default async function FactsPage({ params }: { params: Promise<{ id: string }> }) {
  const c = getCase((await params).id);
  if (!c) notFound();
  return (
    <>
      <div className="section-title">
        <div>
          <h2>Facts from your documents</h2>
          <p>Select a fact to see the exact words it was read from. Fix anything that is wrong; every later step uses these facts.</p>
        </div>
      </div>
      <FactsView facts={c.facts} documents={c.documents} />
    </>
  );
}
