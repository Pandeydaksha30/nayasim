import { redirect } from "next/navigation";
import { EXAMPLE_ID } from "@/lib/case-source";

export default async function CaseIndex({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  // The example has a full report; real cases start at their facts until steps 6-8 exist.
  redirect(`/cases/${id}/${id === EXAMPLE_ID ? "report" : "facts"}`);
}
