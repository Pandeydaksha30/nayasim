import Link from "next/link";
import { Banner, ChevronIcon } from "@/components/icons";
import { loadCase } from "@/lib/case-source";
import { fmtDate } from "@/lib/format";
import { exampleRecordedAt, isExample } from "@/lib/http";
import StepNav from "./step-nav";

const CLAIM: Record<string, string> = {
  delayed_possession: "Delayed possession",
  refund: "Refund",
  other: "Other",
};

function firstFact(facts: { key: string; value: string }[], key: string) {
  return facts.find((f) => f.key === key)?.value;
}

export default async function CaseLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const src = await loadCase(id);
  if (src.kind === "error") {
    return (
      <main className="page page-narrow">
        <div className="crumb"><Link href="/dashboard">Cases</Link></div>
        <Banner tone="error"><b>Could not load this case.</b> {src.message}</Banner>
      </main>
    );
  }

  const c = src.data;
  const example = isExample(id);
  const project = firstFact(c.facts, "project_name");
  const reg = firstFact(c.facts, "rera_registration");
  const status = c.facts.length ? "Facts found" : c.documents.length ? "Documents uploaded" : "New";
  const meta: [string, string, boolean?][] = [
    ["Project", project ?? "Not found yet"],
    ["Registration", reg ?? "Not found yet", !!reg],
    ["Claim", CLAIM[c.claim_type] ?? c.claim_type],
    example ? ["Recorded", fmtDate((await exampleRecordedAt()).slice(0, 10))] : ["Created", fmtDate(c.created_at.slice(0, 10))],
  ];
  const counts = {
    documents: c.documents.length,
    pages: c.documents.reduce((s, d) => s + d.page_count, 0),
    reviewFacts: c.facts_to_check,
    openQuestions: c.questions.filter((q) => !q.answer).length,
    locked: !c.is_demo,
  };

  return (
    <>
      <div className="case-head">
        <div className="case-head-inner">
          <div className="crumb"><Link href="/dashboard">Cases</Link> <ChevronIcon size={12} /> <span>{c.title}</span></div>
          <div className="case-title-row">
            <h1>{c.title}</h1>
            <span className={`tag ${c.facts.length ? "tag-pos" : "tag-neutral"}`}>{status}</span>
            {example && <span className="tag tag-neutral">Recorded example · read-only</span>}
            {!example && c.is_demo && <span className="tag tag-mid">Demo documents</span>}
            {!example && c.shared && <span className="tag tag-neutral">Shared example · read-only</span>}
          </div>
          <dl className="case-meta">
            {meta.map(([label, value, code]) => (
              <div key={label}><dt>{label}</dt><dd className={code ? "code" : undefined}>{value}</dd></div>
            ))}
          </dl>
          {example && (
            <p className="case-note">
              The buyer and the documents in this example are fictional. Everything else is a recording of what NyayaSim
              produced from them: the past orders are real HRERA Gurugram orders, and no figure or quote was written by hand.
            </p>
          )}
        </div>
      </div>
      <div className="case-body">
        <StepNav caseId={id} counts={counts} />
        <main>{children}</main>
      </div>
    </>
  );
}
