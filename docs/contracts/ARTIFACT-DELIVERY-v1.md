# Checked document delivery v1 — candidate

A owns Store/contracts; M owns authenticated HTTP, signed inbound and WhatsApp
media upload/document transport. Additive027 is not deployed. This extends the
original whatsapp_outbound/claim/one-use authorization/result/signed-receipt ledger.
No second sender, public URL, new model call or live authorization is introduced.

## Exact boundary

- `enqueue_checked_artifact_delivery(verified_user, artifact_id) -> {id,state}`:
  EXPLICIT student session or verified linked inbound request only. A draft request
  or completed artifact does not automatically grant attachment delivery. No body,
  recipient, filename, provider media ID or storage URL is accepted from the caller.
  Require current v2 ready artifact, passed latest check, current original citations,
  policy/rubric/source bindings, unpaused agent/current responsibility, act freshness
  and linked phone. Atomically render/store immutable private bytes/check identity
  and enqueue one action per artifact. Repeated/concurrent requests reuse that action
  even after accepted/unknown/failed outcomes; never resend a potentially delivered file.
- `DeliveryClaim.artifact_file_id` is a trailing optional UUID (defaultNone), distinct
  from task_id/offer_id. Database XOR requires exactly one original intent kind.
- `authorize_whatsapp_send(..., supports_documents=False)` keeps old workers safe.
  Only M's completed document transport opts into True. Permitted document results
  carry `ArtifactPayload(kind='artifact',file_id,artifact_id,check_id,filename,
  media_type,sha256,byte_length)` in `SendAuthorization.payload`, with text=None.
  The descriptor contains no URL or private bytes. Existing text/template types remain.
- `read_artifact_delivery_file(claim) -> ArtifactDeliveryFile(descriptor,content)`:
  INTERNAL trusted assembly only, after one-use authorization. Requires the same
  current claim/attempt/link, unexpired lease, persisted matching dispatch descriptor,
  current checked artifact, identical retained bytes/hash and current controls/consent.
  Call before provider upload and again before the document send after upload; confirm
  descriptor/checksum unchanged. No student RPC may accept a delivery claim.

M dispatches only the returned payload, uploads exact private bytes without redirects
or public links, and binds provider media ID to this checksum/account/action locally.
Use a bounded zero-retry upload/send sequence within the claim lease. If private read,
upload, send or result persistence fails after authorization, do not replay the action;
record unknown using existing `record_whatsapp_result` or allow the original abandoned
attempt hold. Existing signed `record_whatsapp_status` reconciles recipient/account/
provider reference. Accepted is not delivered. No live media upload/phone proof exists.

## Gates and limits

Communication consent, quiet hours, pause, current phone generation, source scope/
versions, passed current check, act freshness (1hour) and bytes are checked at dispatch.
File sends require the linked student's current24hour conversation window. Outside
the window they hold with `document_conversation_required`: text/reply/offer templates
cannot carry a document. Ask the student to message first before a bounded phone test;
no document-template approval is claimed or fabricated. One checked DOCX per artifact,
max10MiB, fixed UUID filename and exact MIME. Text-only DOCX uses the same pure serializer
as private downloads; native Word/phone visual acceptance and complex equation/table/
image layout remain unverified/unsupported. No provider IO is in shared/runtime.

Private rendered files are stored in the isolated agent database, never the original
handwriting product. The provider upload must fit the current privacy/activation scope.
Deploying027, sending files, enabling workers and using paid models remain separate
scoped activation decisions; this contract grants none of them.
