import { NextResponse } from "next/server";

/**
 * GET /api/health
 *
 * Frontend liveness probe.
 * Used by the Docker HEALTHCHECK in Dockerfile.frontend.
 * Returns 200 if the Next.js process is running and serving requests.
 */
export async function GET() {
  return NextResponse.json(
    {
      status: "ok",
      service: "sentinel-frontend",
      timestamp: new Date().toISOString(),
    },
    { status: 200 }
  );
}
