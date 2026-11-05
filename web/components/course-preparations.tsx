import type { Preparation } from "../lib/preparations";
import styles from "./course-preparations.module.css";

const label = (value: string) => value.replaceAll("_", " ");

export function CoursePreparations({ records }: { records: Preparation[] }) {
  if (!records.length) return null;
  return (
    <section className={styles.section} aria-label="Private preparation checklists">
      <h4>Preparation checklists</h4>
      <p>
        Original excerpts and questions to help you prepare. These are not completed assignments.
      </p>
      {records.map((record, index) => (
        <article
          key={record.id}
          className={styles.record}
          aria-label={`Preparation for ${record.title}`}
        >
          <details open={index === 0}>
            <summary>
              <span className={styles.title}>{record.title}</span>
              <span className={styles.state}>
                {record.current ? "Current limited evidence" : "Historical checklist"}
              </span>
            </summary>
            <p className={styles.notice}>{record.notice}</p>
            {!record.current && (
              <p className={styles.notice}>
                Source access, evidence or controls have changed. This checklist is historical;
                recheck the originals before using it.
              </p>
            )}
            <p className={styles.meta}>
              Saved {new Date(record.created_at).toLocaleString()}. Current means these limited
              source pins remain inspectable; it does not mean complete evidence or permission to
              submit.
            </p>
            <h5>From the inspected originals</h5>
            {record.excerpts.map((excerpt, i) => (
              <div key={i} className={styles.excerpt}>
                <p>
                  <strong>
                    {excerpt.kind === "student_action"
                      ? "Your action from the original"
                      : "Review from the original"}
                  </strong>{" "}
                  · Source{" "}
                  {record.evidence.findIndex((pin) => pin.object_id === excerpt.object_id) + 1}
                </p>
                <blockquote>{excerpt.quote}</blockquote>
              </div>
            ))}
            <h5>Evidence and remaining gaps</h5>
            <ul className={styles.sources}>
              {record.evidence.map((pin, i) => (
                <li key={pin.object_id}>
                  <p>
                    <strong>Source {i + 1}</strong> · Evidence: {label(pin.coverage)} · Collection:{" "}
                    {label(pin.resource_coverage)}
                  </p>
                  {pin.missing.length > 0 ? (
                    <ul>
                      {pin.missing.map((code, j) => (
                        <li key={j}>{label(code)}</li>
                      ))}
                    </ul>
                  ) : (
                    <p>
                      No item gaps reported in this pin. Other course requirements may still be
                      unread.
                    </p>
                  )}
                  {pin.unread_continuation && (
                    <p className={styles.unread}>More original content remains unread.</p>
                  )}
                </li>
              ))}
            </ul>
            <h5>Questions for you</h5>
            {record.questions.length ? (
              <ul>
                {record.questions.map((question, i) => (
                  <li key={i}>{question}</li>
                ))}
              </ul>
            ) : (
              <p>No clarification questions were saved.</p>
            )}
          </details>
        </article>
      ))}
    </section>
  );
}
