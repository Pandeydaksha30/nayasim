"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { GapQuestion } from "@/lib/demo-case";
import styles from "./questions.module.css";

export default function QuestionsForm({ caseId, questions }: { caseId: string; questions: GapQuestion[] }) {
  const router = useRouter();
  const [answers, setAnswers] = useState<Record<string, string>>(
    Object.fromEntries(questions.filter((q) => q.answer).map((q) => [q.id, q.answer as string])),
  );
  const done = questions.filter((q) => answers[q.id]).length;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        router.push(`/cases/${caseId}/money`);
      }}
    >
      <ol className={styles.list}>
        {questions.map((q, i) => (
          <li key={q.id} className="panel">
            <fieldset className={styles.field}>
              <legend className={styles.legend}>
                <span className="num faint">{i + 1}.</span> {q.question}
              </legend>
              <p className={styles.why}>{q.why}</p>
              <div className={styles.options}>
                {q.options.map((o) => (
                  <label key={o} className={`${styles.option} ${answers[q.id] === o ? styles.optionOn : ""}`}>
                    <input
                      type="radio"
                      name={q.id}
                      value={o}
                      checked={answers[q.id] === o}
                      onChange={() => setAnswers((a) => ({ ...a, [q.id]: o }))}
                    />
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
        <button type="submit" className="btn btn-primary">Save and see money owed</button>
      </div>
    </form>
  );
}
