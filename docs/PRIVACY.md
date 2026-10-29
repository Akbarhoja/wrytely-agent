# Wrytely Academic Agent — Privacy Notice

Effective date: October 29, 2026

This notice covers the Wrytely Academic Agent development pilot, including its student workspace and official WhatsApp integration. Wrytely operates this pilot. The pilot is currently intended for consenting U.S. participants aged 18 or older. For privacy questions and requests, contact **support@wrytely.io**.

This agent is being developed separately from Wrytely’s handwriting service. This notice describes the agent pilot; the handwriting service’s privacy policy remains at https://www.wrytely.io/privacy.

## Information processed

- **Account information:** Clerk processes sign-in information such as your name, email address, profile information and session. The agent uses your Clerk account and session identifiers to associate your private agent and saved work with your account.
- **WhatsApp connection information:** your WhatsApp number, verification challenge records, provider message identifiers, connection state, reply consent, timezone and quiet-hour preferences.
- **Messages and results:** messages you send to the agent, task records, generated answers, model/tool execution records and saved results needed to carry out and review the requested work.
- **Delivery and operational information:** message timestamps, provider acceptance/delivery status, execution attempts, errors and usage information needed for reliability, security and cost control. Infrastructure providers may also process network and request information.

The pilot does not currently connect to Canvas, Teams or calendars. It does not obtain access to your other WhatsApp conversations or address book merely because you message its business number. Do not send passwords, payment-card details, confidential third-party records or unnecessary sensitive information. Use synthetic academic examples during testing.

## How information is used

We use this information to authenticate you, provision your private agent, verify that you control the linked WhatsApp number, receive your messages, generate and save answers, send replies when permitted, honor communication controls, investigate failures and protect the service. Generated responses may contain mistakes and should be checked before use.

## Service providers and sharing

- **Clerk:** account authentication and sessions.
- **Meta WhatsApp Business Platform:** messages sent to and from the agent, phone-number and delivery information, under Meta’s applicable terms and privacy practices.
- **Meta Model API:** the prompt and relevant task context, together with applicable tool definitions/results, are sent to Meta to generate an answer. The pilot uses Muse Spark Standard mode, not Contributor mode. Meta’s published Standard-mode documentation says content is not used to train Meta models. API requests set `store=false`; this does not mean every provider security or operational record is immediately deleted.
- **Railway and its infrastructure providers:** host the agent API and isolated Postgres database and process stored pilot records and operational information.

We do not sell pilot personal information or use it for targeted advertising. We may disclose information when legally required or reasonably necessary to investigate misuse, protect rights or respond to a security incident. Providers may process information in the United States and other countries under their own applicable practices.

## Your controls

You can pause your agent, unlink WhatsApp, and change reply consent, timezone and quiet hours in the workspace. Unlinking stops future use of that connection but does not delete previously saved messages, tasks or results. A request already sent to a provider may not be recalled. Pausing is not account deletion.

For access, correction or deletion requests, email support@wrytely.io. We may need to verify your identity and authority before acting. The pilot does not yet have a self-service account-deletion control. Privacy requests are handled manually, subject to applicable legal requirements and necessary security or legal retention.

## Retention and security

Messages, task results, account links and execution records persist in the pilot database so work can be restored and reviewed. The pilot does not currently apply an automatic fixed retention period. We review records for deletion in response to requests and when ending or changing the pilot, subject to necessary legal and security retention. Provider records and backups may follow separate retention schedules.

We use authenticated account access, ownership checks, signed WhatsApp webhook validation, encrypted network connections and restricted credentials. Authorized pilot operators may access records when needed to run tests, resolve issues or handle privacy requests. No system can guarantee absolute security.

## Changes and contact

We will update this notice as pilot data practices change. Adding course or group-chat connectors or opening the service more broadly requires a further review of this notice and appropriate participant notice before those changes are enabled.

Privacy and deletion requests: **support@wrytely.io**. Include enough information to identify your account, but do not email passwords, verification codes or full payment details.
