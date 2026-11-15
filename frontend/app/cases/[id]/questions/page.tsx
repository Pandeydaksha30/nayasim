import LiveQuestions from "../live/live-questions";
import { loadCase } from "@/lib/case-source";

export const metadata = { title: "Questions" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const src = await loadCase((await params).id);
  return src.kind === "live" ? <LiveQuestions c={src.data} /> : null; // the layout shows the error
}
