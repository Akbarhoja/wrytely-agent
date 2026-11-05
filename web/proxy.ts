import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse, type NextRequest, type NextFetchEvent } from "next/server";
import { authConfigured } from "./lib/config";

const clerk = clerkMiddleware();
export default function proxy(request: NextRequest, event: NextFetchEvent) {
  // Unconfigured builds expose a public shell only; private routes also fail closed.
  if (!authConfigured()) return NextResponse.next();
  return clerk(request, event);
}
export const config = { matcher: ["/((?!_next|.*\\..*).*)", "/api/(.*)"] };
