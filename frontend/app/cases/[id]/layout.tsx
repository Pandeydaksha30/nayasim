import Link from "next/link";
import { notFound } from "next/navigation";
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
          <div className="crumb"><Link href="/">Cases</Link> / {c.title}</div>
          <h1>{c.title}</h1>
          <div className="case-meta">
            <span>Project <b>{c.project}</b>, {c.location}</span>
            <span>Registration <b className="num">{c.reraNo}</b></span>
            <span>Claim <b>{c.claimType}</b></span>
            <span>Updated <b>{fmtDate(c.updated)}</b></span>
          </div>
        </div>
      </div>
      <div className="case-body">
        <StepNav caseId={c.id} openQuestions={c.questions.filter((q) => !q.answer).length} reviewFacts={c.facts.filter((f) => f.confidence === "review").length} />
        <main style={{ minWidth: 0 }}>{children}</main>
      </div>
    </>
  );
}
