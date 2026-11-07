"use client";

import { useEffect, useState } from "react";
import { computeInterest, type InterestOutput } from "@/lib/api";
import { fmtDate, fmtINR, fmtINRShort } from "@/lib/format";
import type { Payment } from "@/lib/types";
import { Banner } from "./icons";
import styles from "./interest-calculator.module.css";

interface Props {
  payments: Payment[];
  possessionPromised: string;
  extensionMonths: number;
  extensionBasis: string;
  ratePct: number;
  rateBasis: string;
  asOf: string;
  editablePayments?: boolean;
}

type State =
  | { kind: "loading" }
  | { kind: "ok"; data: InterestOutput }
  | { kind: "error"; message: string }
  | { kind: "incomplete" };

/** All figures are computed by the Python calculator (POST /api/v1/calculations/interest). */
export default function InterestCalculator(props: Props) {
  const [payments, setPayments] = useState(props.payments);
  const [promised, setPromised] = useState(props.possessionPromised);
  const [ext, setExt] = useState(props.extensionMonths);
  const [rate, setRate] = useState(props.ratePct);
  const [asOf, setAsOf] = useState(props.asOf);
  const [mode, setMode] = useState<"delay" | "refund">("delay");
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const complete = payments.length > 0 && payments.every((p) => p.date && p.amount > 0) && promised && asOf && rate >= 0;
    if (!complete) {
      setState({ kind: "incomplete" });
      return;
    }
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      setState((s) => (s.kind === "ok" ? s : { kind: "loading" }));
      computeInterest(
        { payments, possessionPromised: promised, extensionMonths: ext, annualRatePct: rate, asOf, rateSource: props.rateBasis },
        ctrl.signal,
      )
        .then((data) => setState({ kind: "ok", data }))
        .catch((e: unknown) => {
          if (e instanceof DOMException && e.name === "AbortError") return;
          setState({ kind: "error", message: e instanceof Error ? e.message : "Calculation failed." });
        });
    }, 250);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [payments, promised, ext, rate, asOf, props.rateBasis]);

  const data = state.kind === "ok" ? state.data : null;
  const shown = data ? (mode === "delay" ? data.delay : data.refund) : null;

  function updatePayment(id: string, patch: Partial<Payment>) {
    setPayments((ps) => ps.map((p) => (p.id === id ? { ...p, ...patch } : p)));
  }

  return (
    <div className={styles.wrap}>
      <div className={`panel ${styles.inputs}`}>
        <label>
          <span className="field-label">Promised possession</span>
          <input type="date" value={promised} onChange={(e) => setPromised(e.target.value)} />
        </label>
        <label>
          <span className="field-label">Extension (months)</span>
          <input type="number" min={0} max={60} value={ext} onChange={(e) => setExt(Math.max(0, Number(e.target.value) || 0))} />
        </label>
        <label>
          <span className="field-label">Interest rate (% a year)</span>
          <input type="number" step={0.05} min={0} value={rate} onChange={(e) => setRate(Number(e.target.value) || 0)} />
        </label>
        <label>
          <span className="field-label">Calculate up to</span>
          <input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
        </label>
        <div className={styles.basis}>
          <p>
            <b>Due date used:</b> <span className="num">{data ? fmtDate(data.possession_due) : "—"}</span>. {props.extensionBasis}
          </p>
          <p>
            <b>Rate:</b> {props.rateBasis}
          </p>
        </div>
      </div>

      {state.kind === "error" && (
        <Banner tone="error">
          <b>Could not calculate.</b> {state.message}
        </Banner>
      )}
      {state.kind === "incomplete" && <Banner tone="warn">Fill in every date and amount to see the result.</Banner>}

      <div className={styles.compare} aria-busy={state.kind === "loading"}>
        <button type="button" className={`${styles.option} ${mode === "delay" ? styles.optionOn : ""}`} onClick={() => setMode("delay")}>
          <span className="label">Keep the flat</span>
          <span className={styles.big}>{data ? fmtINRShort(Number(data.delay.interest)) : "…"}</span>
          <span className="small muted">delay interest so far, and it keeps growing until possession</span>
        </button>
        <button type="button" className={`${styles.option} ${mode === "refund" ? styles.optionOn : ""}`} onClick={() => setMode("refund")}>
          <span className="label">Withdraw</span>
          <span className={styles.big}>{data ? fmtINRShort(Number(data.refund.total)) : "…"}</span>
          <span className="small muted">
            {data
              ? `refund of ${fmtINRShort(Number(data.refund.principal))} paid, plus ${fmtINRShort(Number(data.refund.interest))} interest`
              : "refund of everything paid, plus interest"}
          </span>
        </button>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>{mode === "delay" ? "Delay interest, payment by payment" : "Refund interest, payment by payment"}</h3>
          <span className="small faint">{data ? data.method : "Simple interest, 365-day year"}</span>
        </div>
        <div className="table-wrap">
          <table className="ledger">
            <thead>
              <tr>
                <th>Payment</th>
                <th>Paid on</th>
                <th className="r">Amount</th>
                <th>Interest from</th>
                <th className="r">Days</th>
                <th className="r">Interest</th>
              </tr>
            </thead>
            <tbody>
              {payments.map((p, i) => {
                const row = shown?.rows[i];
                return (
                  <tr key={p.id}>
                    <td>{props.editablePayments ? <span className="num">{i + 1}</span> : p.reference}</td>
                    <td className="num">
                      {props.editablePayments ? (
                        <input className={styles.cell} type="date" value={p.date} aria-label={`Payment ${i + 1} date`} onChange={(e) => updatePayment(p.id, { date: e.target.value })} />
                      ) : (
                        fmtDate(p.date)
                      )}
                    </td>
                    <td className="r num">
                      {props.editablePayments ? (
                        <input
                          className={styles.cell}
                          type="number"
                          min={0}
                          step={1000}
                          value={p.amount}
                          aria-label={`Payment ${i + 1} amount`}
                          onChange={(e) => updatePayment(p.id, { amount: Number(e.target.value) || 0 })}
                          style={{ textAlign: "right" }}
                        />
                      ) : (
                        fmtINR(p.amount)
                      )}
                    </td>
                    <td className="num">
                      {row ? fmtDate(row.interest_from) : "—"}
                      {row && mode === "delay" && row.interest_from !== row.paid_on && <span className="faint"> (due date)</span>}
                    </td>
                    <td className="r num">{row ? row.days.toLocaleString("en-IN") : "—"}</td>
                    <td className="r num">{row ? fmtINR(Number(row.interest)) : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
            {shown && (
              <tfoot>
                <tr>
                  <td colSpan={2}>Total</td>
                  <td className="r num">{fmtINR(Number(shown.principal))}</td>
                  <td colSpan={2} />
                  <td className="r num">{fmtINR(Number(shown.interest))}</td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
        {props.editablePayments && (
          <div style={{ padding: "10px 12px", borderTop: "1px solid var(--border)", display: "flex", gap: 8 }}>
            <button
              type="button"
              className="btn"
              onClick={() =>
                setPayments((ps) => [...ps, { id: `p${ps.length + 1}-${ps.at(-1)?.date ?? ""}`, date: ps.at(-1)?.date ?? asOf, amount: 500000, reference: "" }])
              }
            >
              Add payment
            </button>
            {payments.length > 1 && (
              <button type="button" className="btn btn-quiet" onClick={() => setPayments((ps) => ps.slice(0, -1))}>
                Remove last
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
