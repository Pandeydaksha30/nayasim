import LiveDocuments from "../live/live-documents";
import { loadCase } from "@/lib/case-source";

export const metadata = { title: "Documents" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const src = await loadCase((await params).id);
  return src.kind === "live" ? <LiveDocuments c={src.data} /> : null; // the layout shows the error
}
