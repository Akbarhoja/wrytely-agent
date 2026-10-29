type Session = { userId: string | null; getToken: () => Promise<string | null> };
const resourceUuid = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";
const resultRead = new RegExp(
  `^(?:artifacts/${resourceUuid}|responsibilities/${resourceUuid}/artifacts)$`,
  "i",
);
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
  const permitted =
    request.method === "GET"
      ? ["me", "messages", "tasks", "whatsapp", "sources", "responsibilities"].includes(route) ||
        resultRead.test(route) ||
        /^tasks\/[0-9a-f-]{36}$/i.test(route) ||
        /^sources\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(route)
      : request.method === "POST" &&
        [
          "bootstrap",
          "messages",
          "sources",
          "agent/control",
          "whatsapp/link",
          "whatsapp/unlink",
          "whatsapp/preferences",
        ].includes(route);
  if (!permitted) return json(404, "Route not found");
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
    const upstream = await deps.fetch(`${deps.backend.replace(/\/$/, "")}/v1/${route}`, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
      redirect: "error",
    });
    if (upstream.status >= 500)
      return json(503, "Wrytely is having trouble connecting. Please try again.");
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
