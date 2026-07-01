/**
 * GET /api/internal/auth/session
 *
 * Returns the current user if the access token cookie is valid.
 * Used by the client on app load to determine auth state without
 * ever reading the token itself.
 */

import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_INTERNAL_URL ?? "http://backend:8000";

export async function GET(request: NextRequest) {
  const accessToken = request.cookies.get("sentinel_access")?.value;

  if (!accessToken) {
    return NextResponse.json({ user: null }, { status: 401 });
  }

  const backendResponse = await fetch(`${BACKEND_URL}/api/v1/auth/me/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!backendResponse.ok) {
    return NextResponse.json({ user: null }, { status: 401 });
  }

  const user = await backendResponse.json();
  return NextResponse.json({ user });
}
