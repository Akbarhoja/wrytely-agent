type Session = { userId: string | null; getToken: () => Promise<string | null> };
const resourceUuid = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";
const resultRead = new RegExp(
  `^(?:artifacts/${resourceUuid}|responsibilities/${resourceUuid}/(?:artifacts|status))$`,
  "i",
);
const documentList = new RegExp(`^v2/responsibilities/${resourceUuid}/artifacts$`, "i");
const documentDetail = new RegExp(`^v2/artifacts/${resourceUuid}$`, "i");
const documentEvidence = new RegExp(
  `^v2/artifacts/${resourceUuid}/evidence/(?:citation|policy|rubric)/(?:0|[1-9][0-9]{0,5})$`,
  "i",
);
const canvasCoverage = new RegExp(`^source-connections/${resourceUuid}/canvas/coverage$`, "i");
const canvasRevoke = new RegExp(`^source-connections/${resourceUuid}/revoke$`, "i");
const supervisionRead = new RegExp(`^course-supervisions/${resourceUuid}$`, "i");
const supervisionAction = new RegExp(
  `^course-supervisions(?:/${resourceUuid}/(?:pause|notifications|offers/${resourceUuid}/(?:decision|delivery)))?$`,
  "i",
);
const artifactFile = new RegExp(`^v2/artifacts/${resourceUuid}/file$`, "i");
const artifactRevision = new RegExp(`^v2/artifacts/${resourceUuid}/revisions$`, "i");
type Dependencies = {
  configured: boolean;
  backend: string | undefined;
  session: () => Promise<Session>;
  fetch: typeof fetch;
};

function json(status: number, detail: string) {
  return Response.json({ detail }, { status, headers: { "Cache-Control": "no-store" } });
}

export async function forward(request: Request, path: string[], deps: Dependencies) {
  const route = path.join("/");
  const fileRead = artifactFile.test(route);
  const courseRoute = supervisionRead.test(route) || supervisionAction.test(route);
  const documentRead =
    documentList.test(route) || documentDetail.test(route) || documentEvidence.test(route);
  const connectionRead =
    route === "source-connections" ||
    route === "source-connections/canvas/setup" ||
    canvasCoverage.test(route);
  const permitted =
    request.method === "GET"
      ? ["me", "messages", "tasks", "whatsapp", "sources", "responsibilities"].includes(route) ||
        resultRead.test(route) ||
        documentRead ||
        fileRead ||
        supervisionRead.test(route) ||
        connectionRead ||
        /^tasks\/[0-9a-f-]{36}$/i.test(route) ||
        /^sources\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(route)
      : (request.method === "POST" &&
          [
            "bootstrap",
            "messages",
            "sources",
            "responsibilities",
            "agent/control",
            "whatsapp/link",
            "whatsapp/unlink",
            "whatsapp/preferences",
          ].includes(route)) ||
        (request.method === "POST" &&
          (["source-connections/canvas/pairing", "source-connections/canvas/scope"].includes(
            route,
          ) ||
            canvasRevoke.test(route) ||
            supervisionAction.test(route) ||
            artifactRevision.test(route)));
  if (!permitted) return json(404, "Route not found");
  let query = "";
  if (documentRead || connectionRead || fileRead || courseRoute || artifactRevision.test(route)) {
    const url = new URL(request.url);
    const allowed =
      route === "source-connections"
        ? ["limit", "cursor"]
        : canvasCoverage.test(route)
          ? ["limit", "after"]
          : documentList.test(route)
            ? ["limit", "before"]
            : documentEvidence.test(route)
              ? ["check_id", "first_slot", "limit"]
              : [];
    const keys = [...url.searchParams.keys()];
    if (
      url.search.length > 2048 ||
      keys.length !== new Set(keys).size ||
      keys.some((key) => !allowed.includes(key))
    )
      return json(400, "Invalid result request.");
    query = url.search;
  }
  if (request.method === "POST" && request.headers.get("origin") !== new URL(request.url).origin) {
    return json(403, "Request origin not allowed");
  }
  if (!deps.configured || !deps.backend) return json(503, "Your workspace is not connected yet.");
  try {
    const session = await deps.session();
    if (!session.userId) return json(401, "Please sign in to continue.");
    const token = await session.getToken();
    if (!token) return json(401, "Your session expired. Please sign in again.");
    const headers = new Headers({ Authorization: `Bearer ${token}`, Accept: "application/json" });
    let body: string | undefined;
    if (request.method === "POST") {
      if (request.headers.get("content-type")?.split(";")[0] !== "application/json") {
        return json(415, "Use a JSON request.");
      }
      body = await request.text();
      if (new TextEncoder().encode(body).length > 65536) return json(413, "Message is too long.");
      headers.set("Content-Type", "application/json");
      const key = request.headers.get("idempotency-key");
      if (key) headers.set("Idempotency-Key", key);
    }
    const backendPath =
      documentRead || fileRead || artifactRevision.test(route) ? route : `v1/${route}`;
    const upstream = await deps.fetch(`${deps.backend.replace(/\/$/, "")}/${backendPath}${query}`, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
      redirect: "error",
    });
    if (upstream.status >= 500)
      return json(503, "Wrytely is having trouble connecting. Please try again.");
    if (fileRead && upstream.ok) {
      const media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
      if (
        upstream.status !== 200 ||
        upstream.headers.get("content-type") !== media ||
        !upstream.body
      )
        return json(503, "Private file is unavailable.");
      const reader = upstream.body.getReader();
      const chunks: Uint8Array[] = [];
      let size = 0;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.length;
        if (size > 10 * 1024 * 1024) {
          await reader.cancel();
          return json(413, "Private file exceeds the download limit.");
        }
        chunks.push(value);
      }
      const content = new Uint8Array(size);
      let offset = 0;
      for (const chunk of chunks) {
        content.set(chunk, offset);
        offset += chunk.length;
      }
      return new Response(content, {
        headers: {
          "Content-Type": media,
          "Content-Disposition": `attachment; filename="wrytely-${path[2]}.docx"`,
          "Cache-Control": "no-store",
          "X-Content-Type-Options": "nosniff",
        },
      });
    }
    const data = await upstream.json();
    return Response.json(data, {
      status: upstream.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    // Never echo a provider exception, token or request body into the response.
    return json(503, "Wrytely is having trouble connecting. Please try again.");
  }
}
