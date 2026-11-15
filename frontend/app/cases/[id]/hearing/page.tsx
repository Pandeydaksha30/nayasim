import LiveHearing from "../live/live-hearing";
import { loadCase } from "@/lib/case-source";

export const metadata = { title: "Simulated hearing" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const src = await loadCase((await params).id);
  return src.kind === "live" ? <LiveHearing c={src.data} /> : null; // the layout shows the error
}
