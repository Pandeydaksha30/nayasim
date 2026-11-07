import { notFound } from "next/navigation";
import { getCase } from "@/lib/demo-case";
import QuestionsForm from "./questions-form";

export const metadata = { title: "Questions" };

export default async function QuestionsPage({ params }: { params: Promise<{ id: string }> }) {
  const c = getCase((await params).id);
  if (!c) notFound();
  return (
    <>
      <div className="section-title">
        <div>
          <h2>A few things your documents don’t say</h2>
          <p>We only ask what we could not find. Each answer changes the calculation or the arguments, and we say how.</p>
        </div>
      </div>
      <QuestionsForm caseId={c.id} questions={c.questions} />
    </>
  );
}
