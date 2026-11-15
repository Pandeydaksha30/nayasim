"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export interface StepCounts {
  documents: number;
  pages: number;
  /** Facts that still need the buyer's check. */
  reviewFacts: number;
  openQuestions: number;
  /** A private case: steps that send text to the AI model stay closed until a no-retention model is set up. */
  locked: boolean;
}

export default function StepNav({ caseId, counts }: { caseId: string; counts: StepCounts }) {
  const path = usePathname();
  const closed = "Closed for private cases";
  const steps = [
    { slug: "documents", label: "Documents", sub: `${counts.documents} ${counts.documents === 1 ? "file" : "files"}, ${counts.pages} pages` },
    { slug: "facts", label: "Facts", sub: counts.reviewFacts ? `${counts.reviewFacts} to check` : "On the page they came from" },
    { slug: "ask", label: "Ask your documents", sub: counts.locked ? "Passage search" : "Cited answers" },
    { slug: "questions", label: "Questions", sub: counts.openQuestions ? `${counts.openQuestions} unanswered` : "Done" },
    { slug: "money", label: "Money owed", sub: "Interest and refund" },
    { slug: "agent", label: "Agent analysis", sub: counts.locked ? closed : "Tools chosen step by step", locked: counts.locked },
    { slug: "hearing", label: "Simulated hearing", sub: counts.locked ? closed : "Arguments and bench", locked: counts.locked },
    { slug: "report", label: "Report", sub: "Outcome and weak points" },
    { slug: "draft", label: "Complaint draft", sub: "Built from checked facts" },
  ];
  return (
    <nav aria-label="Case steps">
      <ol className="steps">
        {steps.map((s, i) => {
          const href = `/cases/${caseId}/${s.slug}`;
          return (
            <li key={s.slug}>
              <Link href={href} aria-current={path === href ? "page" : undefined} className={s.locked ? "step-locked" : undefined}>
                <span className="n">{i + 1}</span>
                <span>
                  {s.label}
                  <span className="sub">{s.sub}</span>
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
