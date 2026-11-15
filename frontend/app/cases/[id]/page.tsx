import { redirect } from "next/navigation";
import { isExample } from "@/lib/http";

export default async function CaseIndex({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  // The example opens on its report; your own case starts with its facts.
  redirect(`/cases/${id}/${isExample(id) ? "report" : "facts"}`);
}
