import { loadCase } from "@/lib/case-source";
import AgentClient from "./agent-client";

export const metadata = { title: "Agent analysis" };

export default async function AgentPage({ params }: { params: Promise<{ id: string }> }) {
  const src = await loadCase((await params).id);
  if (src.kind === "error") return null; // the layout shows the error
  return <AgentClient caseId={src.data.id} isDemo={src.data.is_demo} readOnly={src.data.shared} />;
}
