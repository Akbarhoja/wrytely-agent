# M2 academic ownership scenario

Status: prepared, not executed. Owner split: Murtazo owns intake, connectors,
student delegation and result presentation; Codex owns planner, memory, drafting
and verification. Approved preparation while Meta business setup is deferred;
M1 remains incomplete. No A4 implementation is authorized by this document.

## Student outcome

Cedar has several courses and a group project. A commitment appears in the
controlled project conversation. Wrytely identifies Cedar's part, asks whether to
take it on, and, after one explicit delegation, independently produces a checked
comparison draft. Cedar can inspect the saved work without prompting every step.

All names, course details, studies and findings below are fictional fixtures.
They must never be presented as real research, actual Canvas data, or evidence
that a live Teams connector works. A controlled-group ingestion run needs real
consenting participants; loading this text manually only proves snapshot intake.
No messages go to classmates or instructors. No assignment is submitted.

## Inputs

Use four separate versioned observations. Set retrieved_at to the actual aware
ingestion time. The source identifiers below are stable fixture identifiers, not
network endpoints. An uploaded or pasted input has coverage=snapshot even if its
title mentions an academic system. Only actual connector observations may claim
api/feed/group coverage. Bind the four source IDs to Cedar's responsibility using
the existing Store; never accept a browser-supplied owner ID.

### 1. Assignment and policy

source_key: m2-demo/assignment; external_revision: v1;
reference: synthetic:m2/assignment/v1; title: Fictional seminar assignment.

```text
FICTIONAL COURSE: Introduction to Learning Research, DEMO 101.
Assignment: Compare two supplied fictional studies of study habits.
Write a 250–300 word draft comparing recall outcomes and one limitation.
Use only Source A and Source B supplied with this assignment.
Compare both studies using their participant counts and reported recall outcomes.
Explain that these results cannot establish which method works best for everyone.
Include at least one exact quotation from each source with its source label.
End with one practical recommendation that acknowledges uncertainty.
AI drafting is permitted with disclosure. The student must review all claims.
Include this disclosure separately from the word-counted body:
Draft prepared with Wrytely AI; student review is required.
The assigned group section is due October 30, 2026 at 18:00 America/Denver.
```

### 2. Source A

source_key: m2-demo/source-a; external_revision: v1;
reference: synthetic:m2/source-a/v1; title: Fictional Source A.

```text
FICTIONAL DEMONSTRATION DATA — not a published study.
Source A: A small study of spaced practice.
Source A included 20 participants.
Participants practiced vocabulary in three sessions across one week.
Mean recall on the study quiz was 75 percent.
The study had no randomized comparison group.
The findings describe this sample and do not establish a universal benefit.
```

### 3. Source B

source_key: m2-demo/source-b; external_revision: v1;
reference: synthetic:m2/source-b/v1; title: Fictional Source B.

```text
FICTIONAL DEMONSTRATION DATA — not a published study.
Source B: A small study of a single review session.
Source B included 18 participants.
Participants practiced different vocabulary in one session before the quiz.
Mean recall on the study quiz was 68 percent.
The studies used different vocabulary and different participants.
The difference in quiz scores cannot establish a causal advantage for either method.
```

### 4. Group commitment

source_key: m2-demo/group-message; external_revision: message-1;
reference: synthetic:m2/group/message-1; title: Controlled group commitment.

```text
FICTIONAL GROUP CONVERSATION — use consenting participants for a live connector run.
Teammate: Cedar, please take the comparison section for DEMO 101. Use the two
provided sources and the assignment rubric. We need your draft by Friday,
October 30 at 6 pm Denver time. I will handle the introduction.
Cedar: Yes, I will take the comparison section.
```

## Delegation and expected autonomous work

The agent first identifies the commitment with its group-message evidence. A group
message alone is not authorization to draft, share or submit work. Present a
delegation question with the section, deadline and intended private deliverable.
The test student then provides this one instruction:

> Take responsibility for my comparison section. Read the supplied assignment
> and both sources, prepare a draft, and check its claims, quotations and rubric
> coverage. Save it privately for my review. Do not share or submit it.

After delegation, freeze external inputs. Observe the agent choosing useful steps
such as extracting requirements, comparing evidence, drafting and checking. The
operator must not select each next step or insert more student prompts to make
continuation happen. Internal trusted drafting configuration may be recorded as
setup evidence, but is not proof of automatic student-facing delegation.

At least one useful task must be selected by the agent after the initial work,
and progress must continue across an episode boundary using persisted context.
Do not require exactly this illustrative step order or repeated work to fill time.
When ready, save the result and a short student-facing status. WhatsApp delivery
remains a separate M1 dependency; a saved web result is not a delivered message.

## Existing boundaries to reuse

- SourceObservation in contracts/models.py; Store.observe_source and bind_source.
- Existing responsibility creation, planner and bounded runtime.worker.run_once.
- CoursePolicy and RubricItem in contracts/artifacts.py, with exact quotes and
  actual stored version IDs. Policy evidence is the drafting/disclosure sentence
  above; requirement evidence comes from the same assignment observation.
- Store.configure_drafting_task only through trusted assembly after authorization.
  Ordinary conversation content cannot grant itself drafting authority.
- Existing generate_checked_draft and mandatory verification; the model must not
  set artifact readiness directly. Saved reports must remain inspectable.

Current gaps to resolve through Murtazo's B2 claim and shared interface agreement:
student context intake, controlled-group ingestion, commitment/delegation API,
automatic source-backed policy/rubric extraction and private artifact presentation.
Existing unit tests or direct Store setup do not prove those product paths.
Do not add duplicate clients, storage, planners or a second conversation product.

## Observable acceptance

| Check | Required observation |
|---|---|
| Intake | Four private source observations with provenance, versions and honest coverage |
| Commitment | Cedar's section and deadline identified with group-message evidence |
| Delegation | One explicit student authorization; no automatic sharing/submission |
| Continuation | Multiple useful steps, at least one agent-created next task, no new inputs |
| Persistence | Saved context/progress reused across an episode boundary |
| Draft | 250–300 body words; both sample sizes/outcomes; quotes from both sources |
| Limits | Different samples/materials and lack of causal inference acknowledged |
| Checks | Stored exact-quote, claim, rubric and disclosure reports; failures remain visible |
| Result | Current private artifact available for student review; no external share |
| Isolation | A second authenticated student cannot read Cedar's sources/work/artifact |

Word-count and scenario-specific content must be checked explicitly; a general
model assessment is not evidence that every numeric requirement was enforced.
Model-assessed support is fallible and must not be described as proof of truth.

Record exact commit, input path (manual snapshot or actual connector), permitted
model calls/spend, task transitions and result/check evidence. Live model execution
of M2 needs its own confirmed bounded scope; the existing M1 authorization is not
blanket permission for an unattended academic workload. Do not mark M2 passed
until the complete integrated path runs. Changed requirements are the later M3/A4
exercise and are deliberately excluded here.
