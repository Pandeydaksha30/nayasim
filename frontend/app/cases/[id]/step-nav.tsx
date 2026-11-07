"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function StepNav({ caseId, openQuestions, reviewFacts }: { caseId: string; openQuestions: number; reviewFacts: number }) {
  const path = usePathname();
  const steps = [
    { slug: "documents", label: "Documents", sub: "4 files, 47 pages" },
    { slug: "facts", label: "Facts", sub: reviewFacts ? `${reviewFacts} to check` : "All checked" },
    { slug: "questions", label: "Questions", sub: openQuestions ? `${openQuestions} unanswered` : "Done" },
    { slug: "money", label: "Money owed", sub: "Interest and refund" },
    { slug: "hearing", label: "Simulated hearing", sub: "3 rounds" },
    { slug: "report", label: "Report", sub: "Outcome and weak points" },
    { slug: "draft", label: "Complaint draft", sub: "UP RERA format" },
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
