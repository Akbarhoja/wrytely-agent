import type { NextConfig } from "next";

const config: NextConfig = {
  // Preserve the request's actual origin for Clerk's same-URL rewrite. Converting
  // 127.0.0.1 to localhost makes Next treat it as an external proxy back to itself.
  skipProxyUrlNormalize: true,
  turbopack: { root: process.cwd() },
  outputFileTracingRoot: process.cwd(),
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};
export default config;
