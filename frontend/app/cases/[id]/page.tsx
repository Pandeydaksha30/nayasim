import { redirect } from "next/navigation";

export default async function CaseIndex({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/cases/${id}/report`);
}
