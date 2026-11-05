# Wrytely Academic Agent — Privacy Notice

Effective date: November 4, 2026

This notice covers the Wrytely Academic Agent development pilot, including its student workspace, Canvas collection extension and official WhatsApp and Telegram bot integrations. Wrytely operates this pilot. The pilot is currently intended for consenting U.S. participants aged 18 or older. For privacy questions and requests, contact **support@wrytely.io**.

This agent is being developed separately from Wrytely’s handwriting service. This notice describes the agent pilot; the handwriting service’s privacy policy remains at https://www.wrytely.io/privacy.

## Information processed

- **Account information:** Clerk processes sign-in information such as your name, email address, profile information and session. The agent uses your Clerk account and session identifiers to associate your private agent and saved work with your account.
- **WhatsApp connection information:** your WhatsApp number, verification challenge records, provider message identifiers, connection state, reply consent, timezone and quiet-hour preferences.
- **Telegram connection information:** the private numeric chat identifier, bot identity, one-use pairing challenge records, link generation, provider update/message identifiers, separate reply and preparation-notification consent, timezone and quiet-hour preferences. Telegram usernames are not proof of Wrytely identity.
- **Messages and results:** messages you send to the agent, task records, generated answers, model/tool execution records and saved results needed to carry out and review the requested work.
- **Canvas course information you authorize us to collect:** discovered course names/identifiers, selected syllabus and course-page text, assignment instructions, rubrics and dates, announcements, visible discussions/replies, modules/items, your submission status/content/feedback, your assignment grades, readable course files and extracted document text. Connection identity, selected scope, observations, version history and coverage records associate this information with your account.
- **Delivery and operational information:** message timestamps, provider acceptance/delivery status, execution attempts, errors and usage information needed for reliability, security and cost control. Infrastructure providers may also process network and request information.

The Chrome extension reads from your signed-in Canvas session only after you pair it, verify the account, choose scope and enable collection. It uploads selected course information to Wrytely's isolated Railway pilot backend and database. It does not export your Canvas password or cookies. Collection pauses when Chrome/session access is unavailable; stored information may remain out of date until another sync. Teams, other WhatsApp conversations/address books and calendars are not connected by this pilot.

Choose courses you are authorized to share and avoid unnecessary third-party confidential data. Do not send passwords, payment-card details, confidential third-party records or unnecessary sensitive information. Use synthetic examples unless you explicitly agree to a scoped real-data pilot test.

## How information is used

We use this information to authenticate you, provision your private agent, verify that you control the linked WhatsApp number or Telegram private chat, receive your messages, generate and save answers, send replies when permitted, honor communication controls, investigate failures and protect the service. Generated responses may contain mistakes and should be checked before use.

We store and version authorized course information so your agent can retrieve original evidence, identify changes and support academic work you delegate. Relevant authorized course context may be sent to the configured Meta-model inference provider when a separately enabled model task needs it. Collection itself does not require model inference. The development pilot can use the Meta Model API or Fireworks to serve a Meta model, depending on operator configuration. Generated interpretations and drafts require review.

## Service providers and sharing

- **Clerk:** account authentication and sessions.
- **Meta WhatsApp Business Platform:** messages sent to and from the agent, phone-number and delivery information, under Meta’s applicable terms and privacy practices.
- **Telegram:** private bot messages and attachments, chat/message/update identifiers and delivery requests under Telegram's own terms and privacy practices. Preparation outputs may contain selected course excerpts, clarification questions and coverage warnings. The pilot does not read other Telegram conversations, groups or contacts.
- **Fireworks:** when selected, prompts, relevant authorized course context and applicable tool definitions/results are sent to Fireworks to run the configured Meta model. Fireworks processing and retention follow its own applicable practices; Meta Model API Standard-mode statements below are not promises about Fireworks.
- **Meta Model API:** the prompt and relevant task context, together with applicable tool definitions/results, are sent to Meta to generate an answer. When the Meta Model API is selected, requests use the configured pilot team and set `store=false`. This setting does not mean every provider security or operational record is immediately deleted. Provider processing follows its applicable terms and privacy practices.
- **Railway and its infrastructure providers:** host the agent API and isolated Postgres database and process stored pilot records and operational information.

We do not sell pilot personal information or use it for targeted advertising. We may disclose information when legally required or reasonably necessary to investigate misuse, protect rights or respond to a security incident. Providers may process information in the United States and other countries under their own applicable practices.

## Your controls

You can pause your agent, unlink WhatsApp or Telegram, and change the separate channel consents, timezone and quiet hours in the workspace. Telegram reply and preparation-notification consents start disabled. Sending /stop to the linked Telegram bot pauses Wrytely and disables Telegram messages. A preparation checklist preserves original excerpts and gaps; it is not a submitted, completed or checked assignment. Unlinking stops future use of that connection but does not delete previously saved messages, tasks or results. A request already sent to a provider may not be recalled. Pausing is not account deletion.

You can select courses/content, disable collection locally or disconnect Canvas in the workspace. Disconnecting invalidates that connection and blocks new authenticated reads/uploads; it does not automatically erase previously saved records. A request already in flight cannot be recalled, but control checks prevent it from committing or returning content after invalidation. Source-derived private results can become unavailable when source access changes.

For access, correction or deletion requests, email support@wrytely.io. We may need to verify your identity and authority before acting. The pilot does not yet have a self-service account-deletion control. Privacy requests are handled manually, subject to applicable legal requirements and necessary security or legal retention.

## Retention and security

Messages, task results, account links and execution records persist in the pilot database so work can be restored and reviewed. The pilot does not currently apply an automatic fixed retention period. We review records for deletion in response to requests and when ending or changing the pilot, subject to necessary legal and security retention. Provider records and backups may follow separate retention schedules.

We use authenticated account access, ownership checks, signed WhatsApp webhook validation, secret-authenticated Telegram callbacks, encrypted network connections and restricted credentials. Authorized pilot operators may access records when needed to run tests, resolve issues or handle privacy requests. No system can guarantee absolute security.

## Changes and contact

We will update this notice as pilot data practices change. Adding course or group-chat connectors or opening the service more broadly requires a further review of this notice and appropriate participant notice before those changes are enabled.

Privacy and deletion requests: **support@wrytely.io**. Include enough information to identify your account, but do not email passwords, verification codes or full payment details.
