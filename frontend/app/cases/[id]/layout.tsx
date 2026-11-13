import Link from "next/link";
import { Banner, ChevronIcon } from "@/components/icons";
import { loadCase } from "@/lib/case-source";
import { fmtDate } from "@/lib/format";
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

  let head: { title: string; status: string; meta: [string, string, boolean?][] };
  let counts;
  if (src.kind === "example") {
    const c = src.data;
    head = {
      title: c.title,
      status: c.status,
      meta: [
        ["Project", `${c.project}, ${c.location}`],
        ["Registration", c.reraNo, true],
        ["Claim", c.claimType],
        ["Last updated", fmtDate(c.updated)],
      ],
    };
    counts = {
      documents: c.documents.length,
      pages: c.documents.reduce((s, d) => s + d.pages, 0),
      reviewFacts: c.facts.filter((f) => f.confidence === "review").length,
      openQuestions: c.questions.filter((q) => !q.answer).length,
      analysisBuilt: true,
      draftBuilt: true,
    };
  } else {
    const c = src.data;
    const project = firstFact(c.facts, "project_name");
    const reg = firstFact(c.facts, "rera_registration");
    head = {
      title: c.title,
      status: c.facts.length ? "Facts found" : c.documents.length ? "Documents uploaded" : "New",
      meta: [
        ["Project", project ?? "Not found yet"],
        ["Registration", reg ?? "Not found yet", !!reg],
        ["Claim", CLAIM[c.claim_type] ?? c.claim_type],
        ["Created", fmtDate(c.created_at.slice(0, 10))],
      ],
    };
    counts = {
      documents: c.documents.length,
      pages: c.documents.reduce((s, d) => s + d.page_count, 0),
      reviewFacts: c.facts.filter((f) => f.confidence === "review" && !f.confirmed).length,
      openQuestions: c.questions.filter((q) => !q.answer).length,
      analysisBuilt: true,
      draftBuilt: true,
    };
  }

  return (
    <>
      <div className="case-head">
        <div className="case-head-inner">
          <div className="crumb"><Link href="/dashboard">Cases</Link> <ChevronIcon size={12} /> <span>{head.title}</span></div>
          <div className="case-title-row">
            <h1>{head.title}</h1>
            <span className="tag tag-pos">{head.status}</span>
            {src.kind === "example" && <span className="tag tag-neutral">Example</span>}
            {src.kind === "live" && src.data.is_demo && <span className="tag tag-mid">Demo documents</span>}
            {src.kind === "live" && src.data.shared && <span className="tag tag-neutral">Shared example · read-only</span>}
          </div>
          <dl className="case-meta">
            {head.meta.map(([label, value, code]) => (
              <div key={label}><dt>{label}</dt><dd className={code ? "code" : undefined}>{value}</dd></div>
            ))}
          </dl>
        </div>
      </div>
      <div className="case-body">
        <StepNav caseId={id} counts={counts} />
        <main>{children}</main>
      </div>
    </>
  );
}
