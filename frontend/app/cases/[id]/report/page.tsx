import LiveReport from "../live/live-report";
import { loadCase } from "@/lib/case-source";

export const metadata = { title: "Report" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const src = await loadCase((await params).id);
  return src.kind === "live" ? <LiveReport c={src.data} /> : null; // the layout shows the error
}
