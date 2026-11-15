import LiveMoney from "../live/live-money";
import { loadCase } from "@/lib/case-source";

export const metadata = { title: "Money owed" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const src = await loadCase((await params).id);
  return src.kind === "live" ? <LiveMoney c={src.data} /> : null; // the layout shows the error
}
