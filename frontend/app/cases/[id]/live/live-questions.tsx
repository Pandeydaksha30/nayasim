"use client";

import Link from "next/link";
import { useState } from "react";
import { Banner } from "@/components/icons";
import { answerQuestion, type CaseFull, type CaseQuestion } from "@/lib/cases-api";
import styles from "../questions/questions.module.css";

export default function LiveQuestions({ c }: { c: CaseFull }) {
  const [questions, setQuestions] = useState<CaseQuestion[]>(c.questions);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function choose(q: CaseQuestion, option: string) {
    setSaving(q.id);
    setError(null);
    try {
      const updated = await answerQuestion(c.id, q.id, option);
      setQuestions(updated.questions); // the server decides which questions still apply
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save the answer.");
    } finally {
      setSaving(null);
    }
  }

  const done = questions.filter((q) => q.answer).length;
  return (
    <>
      <div className="section-title">
        <div>
          <h2>A few things your documents don’t say</h2>
          <p>We only ask about what we could not find. Answers are saved as you choose them.</p>
        </div>
      </div>
      {error && <div style={{ marginBottom: 12 }}><Banner tone="error"><b>Not saved.</b> {error}</Banner></div>}
      <ol className={styles.list}>
        {questions.map((q, i) => (
          <li key={q.id} className="panel">
            <fieldset className={styles.field} disabled={saving === q.id}>
              <legend className={styles.legend}>
                <span className={`${styles.qn} ${q.answer ? styles.qnDone : ""}`}>{i + 1}</span>
                <span>{q.question}</span>
              </legend>
              <p className={styles.why}>{q.why}</p>
              <div className={styles.options}>
                {q.options.map((o) => (
                  <label key={o} className={`${styles.option} ${q.answer === o ? styles.optionOn : ""}`}>
                    <input type="radio" name={q.id} value={o} checked={q.answer === o} onChange={() => choose(q, o)} />
                    {o}
                  </label>
                ))}
              </div>
            </fieldset>
          </li>
        ))}
      </ol>
      <div className={styles.bar}>
        <span className="small muted">{done} of {questions.length} answered</span>
        <Link className="btn btn-primary" href={`/cases/${c.id}/money`}>See money owed</Link>
      </div>
    </>
  );
}
