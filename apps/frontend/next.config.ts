import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output for minimal Docker image (see Dockerfile.frontend)
  output: "standalone",

  // Keep development output separate from production builds in Compose.
  distDir: process.env.NEXT_DIST_DIR ?? ".next",

  // Security headers
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "geolocation=(), microphone=(), camera=()",
          },
        ],
      },
    ];
  },

  // Proxy API calls to backend in development (avoids CORS)
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    return [
      {
        source: "/api/backend/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },

  // Strict mode for catching React issues early
  reactStrictMode: true,
};

export default nextConfig;
