import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronIcon } from "@/components/icons";
import { getCase } from "@/lib/demo-case";
import { fmtDate } from "@/lib/format";
import StepNav from "./step-nav";

export default async function CaseLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const c = getCase(id);
  if (!c) notFound();

  return (
    <>
      <div className="case-head">
        <div className="case-head-inner">
          <div className="crumb"><Link href="/">Cases</Link> <ChevronIcon size={12} /> <span>{c.title}</span></div>
          <div className="case-title-row">
            <h1>{c.title}</h1>
            <span className="tag tag-pos">{c.status}</span>
          </div>
          <dl className="case-meta">
            <div><dt>Project</dt><dd>{c.project}, {c.location}</dd></div>
            <div><dt>Registration</dt><dd className="code">{c.reraNo}</dd></div>
            <div><dt>Claim</dt><dd>{c.claimType}</dd></div>
            <div><dt>Last updated</dt><dd>{fmtDate(c.updated)}</dd></div>
          </dl>
        </div>
      </div>
      <div className="case-body">
        <StepNav
          caseId={c.id}
          openQuestions={c.questions.filter((q) => !q.answer).length}
          reviewFacts={c.facts.filter((f) => f.confidence === "review").length}
        />
        <main>{children}</main>
      </div>
    </>
  );
}
