/**
 * POST /api/internal/auth/logout
 *
 * Blacklists the refresh token on the backend (see AuthService.logout in
 * Phase 2), then clears both cookies regardless of backend response —
 * the user should always be logged out client-side even if the backend
 * call fails for some reason.
 */

import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_INTERNAL_URL ?? "http://backend:8000";

export async function POST(request: NextRequest) {
  const accessToken = request.cookies.get("sentinel_access")?.value;
  const refreshToken = request.cookies.get("sentinel_refresh")?.value;

  if (accessToken && refreshToken) {
    try {
      await fetch(`${BACKEND_URL}/api/v1/auth/logout/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ refresh: refreshToken }),
      });
    } catch {
      // Backend call failed — still clear cookies client-side below
    }
  }

  const response = NextResponse.json({ success: true });
  response.cookies.delete("sentinel_access");
  response.cookies.delete("sentinel_refresh");
  return response;
}
