# Canvas pilot privacy amendment — draft for Akbar's review

This is a proposed factual amendment to [the effective privacy notice](PRIVACY.md),
not an effective notice or legal-compliance certification. The existing approved
notice must not say Canvas is disconnected once real collection is enabled.
Leave the existing notice unchanged until the supervisor reviews this amendment.

Proposed changes when the Canvas pilot begins:

- Add Canvas to the development-pilot scope and update the effective date.
- Add: “Canvas course information you authorize us to collect: discovered course
  names/identifiers, selected syllabus and course-page text, assignment instructions,
  rubrics and dates, announcements, visible discussions/replies, modules/items, your
  submission status/content/feedback, your assignment grades, readable course files
  and extracted document text. Connection identity, selected scope, observations,
  version history and coverage records associate this information with your account.”
- Replace the disconnected-Canvas sentence with: “The Chrome extension reads from
  your signed-in Canvas session only after you pair it, verify the account, choose
  scope and enable collection. It uploads selected course information to Wrytely's
  isolated Railway pilot backend and database. It does not export your Canvas
  password or cookies. Collection pauses when Chrome/session access is unavailable;
  stored information may remain out of date until another sync. Teams, other
  WhatsApp conversations/address books and calendars are not connected by this pilot.”
- Add to use: “We store and version authorized course information so your agent can
  retrieve original evidence, identify changes and support academic work you delegate.
  Relevant authorized course context may be sent to the Meta Model API when a
  separately enabled model task needs it. No model calls are part of the bounded
  P1 collection test. Generated interpretations and drafts require review.”
- Add to controls: “You can select courses/content, disable collection locally or
  disconnect Canvas in the workspace. Disconnecting invalidates that connection
  and blocks new authenticated reads/uploads; it does not automatically erase
  previously saved records. A request already in flight cannot be recalled, but
  control checks prevent it from committing or returning content after invalidation.
  Source-derived private results can become unavailable when source access changes.”
- Keep existing Clerk/Meta/Railway processing disclosures, manual privacy requests
  at support@wrytely.io and the absence of an automatic fixed retention deadline.
  Do not promise deletion on disconnect or assert legal/institutional compliance.
- Keep the consenting-adult pilot restriction. Ask participants to choose courses
  they are authorized to share and avoid unnecessary third-party confidential data.

Approval should identify this exact amendment before it replaces the effective
notice. Publishing a technical candidate does not itself authorize real collection.
