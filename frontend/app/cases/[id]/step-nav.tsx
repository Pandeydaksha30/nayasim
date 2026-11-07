"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export interface StepCounts {
  documents: number;
  pages: number;
  reviewFacts: number;
  openQuestions: number;
  /** Steps 6-8 (hearing, report, draft) exist only for the example case so far. */
  analysisBuilt: boolean;
}

export default function StepNav({ caseId, counts }: { caseId: string; counts: StepCounts }) {
  const path = usePathname();
  const later = "Not built yet";
  const steps = [
    { slug: "documents", label: "Documents", sub: `${counts.documents} files, ${counts.pages} pages` },
    { slug: "facts", label: "Facts", sub: counts.reviewFacts ? `${counts.reviewFacts} to check` : "All checked" },
    { slug: "questions", label: "Questions", sub: counts.openQuestions ? `${counts.openQuestions} unanswered` : "Done" },
    { slug: "money", label: "Money owed", sub: "Interest and refund" },
    { slug: "hearing", label: "Simulated hearing", sub: counts.analysisBuilt ? "3 rounds" : later },
    { slug: "report", label: "Report", sub: counts.analysisBuilt ? "Outcome and weak points" : later },
    { slug: "draft", label: "Complaint draft", sub: counts.analysisBuilt ? "Complaint format" : later },
  ];

  return (
    <nav aria-label="Case steps">
      <ol className="steps">
        {steps.map((s, i) => {
          const href = `/cases/${caseId}/${s.slug}`;
          return (
            <li key={s.slug}>
              <Link href={href} aria-current={path === href ? "page" : undefined}>
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
