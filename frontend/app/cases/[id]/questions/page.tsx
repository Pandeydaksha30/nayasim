import LiveQuestions from "../live/live-questions";
import { loadCase } from "@/lib/case-source";
import QuestionsForm from "./questions-form";

export const metadata = { title: "Questions" };

export default async function QuestionsPage({ params }: { params: Promise<{ id: string }> }) {
  const src = await loadCase((await params).id);
  if (src.kind === "live") return <LiveQuestions c={src.data} />;
  if (src.kind !== "example") return null; // the layout shows the error
  const c = src.data;
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
