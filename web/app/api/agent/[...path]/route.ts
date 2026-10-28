import { auth } from "@clerk/nextjs/server";
import { authConfigured } from "@/lib/config";
import { forward } from "@/lib/forward";

export const dynamic = "force-dynamic";
async function handle(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  return forward(request, path, {
    configured: authConfigured(),
    backend: process.env.AGENT_API_URL,
    session: auth,
    fetch,
  });
}
export { handle as GET, handle as POST };
