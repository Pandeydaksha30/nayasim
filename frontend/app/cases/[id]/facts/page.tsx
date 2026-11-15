import LiveFacts from "../live/live-facts";
import { loadCase } from "@/lib/case-source";

export const metadata = { title: "Facts" };

export default async function FactsPage({ params }: { params: Promise<{ id: string }> }) {
  const src = await loadCase((await params).id);
  return src.kind === "live" ? <LiveFacts c={src.data} /> : null; // the layout shows the error
}
