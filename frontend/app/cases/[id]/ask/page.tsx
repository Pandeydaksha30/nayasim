import { Banner } from "@/components/icons";
import { loadCase } from "@/lib/case-source";
import AskClient from "./ask-client";

export const metadata = { title: "Ask your documents" };

export default async function AskPage({ params }: { params: Promise<{ id: string }> }) {
  const src = await loadCase((await params).id);
  if (src.kind === "error") return null; // the layout shows the error
  if (src.kind === "example")
    return (
      <Banner tone="info">
        The static example has no stored documents. Create a demo case on the dashboard, upload a sample document, and ask
        it questions there.
      </Banner>
    );
  return <AskClient caseId={src.data.id} isDemo={src.data.is_demo} />;
}
