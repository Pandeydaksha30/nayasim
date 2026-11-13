import { Banner } from "@/components/icons";
import { loadCase } from "@/lib/case-source";
import AgentClient from "./agent-client";

export const metadata = { title: "Agent analysis" };

export default async function AgentPage({ params }: { params: Promise<{ id: string }> }) {
  const src = await loadCase((await params).id);
  if (src.kind === "error") return null;
  if (src.kind === "example")
    return (
      <Banner tone="info">
        The static example has no stored documents. Create a demo case on the dashboard to run an agent analysis.
      </Banner>
    );
  return <AgentClient caseId={src.data.id} isDemo={src.data.is_demo} />;
}
