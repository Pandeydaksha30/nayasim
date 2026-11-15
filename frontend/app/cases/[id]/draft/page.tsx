import LiveDraft from "../live/live-draft";
import { loadCase } from "@/lib/case-source";

export const metadata = { title: "Complaint draft" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const src = await loadCase((await params).id);
  return src.kind === "live" ? <LiveDraft c={src.data} /> : null; // the layout shows the error
}
