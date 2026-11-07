import LiveFacts from "../live/live-facts";
import { loadCase } from "@/lib/case-source";
import FactsView from "./facts-view";

export const metadata = { title: "Facts" };

export default async function FactsPage({ params }: { params: Promise<{ id: string }> }) {
  const src = await loadCase((await params).id);
  if (src.kind === "live") return <LiveFacts c={src.data} />;
  if (src.kind !== "example") return null; // the layout shows the error
  const c = src.data;
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
