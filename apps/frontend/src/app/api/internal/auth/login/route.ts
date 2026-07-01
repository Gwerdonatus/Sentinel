/**
 * POST /api/internal/auth/login
 *
 * Backend-for-frontend login. Calls Django, then stores the access and
 * refresh tokens in httpOnly cookies — never exposed to client JavaScript.
 *
 * This is the only safe pattern for JWT storage in a security product.
 * Storing tokens in localStorage or a client-readable cookie would
 * undermine everything Sentinel's backend does to protect them (rotation,
 * blacklisting, short access token lifetime) — an XSS vulnerability
 * anywhere in the frontend would leak the token directly.
 */

import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_INTERNAL_URL ?? "http://backend:8000";

const ACCESS_TOKEN_COOKIE = "sentinel_access";
const REFRESH_TOKEN_COOKIE = "sentinel_refresh";

// Matches backend JWT_ACCESS_TOKEN_LIFETIME_MINUTES / JWT_REFRESH_TOKEN_LIFETIME_DAYS
const ACCESS_TOKEN_MAX_AGE = 15 * 60; // 15 minutes
const REFRESH_TOKEN_MAX_AGE = 7 * 24 * 60 * 60; // 7 days

export async function POST(request: NextRequest) {
  const body = await request.json();

  const backendResponse = await fetch(`${BACKEND_URL}/api/v1/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await backendResponse.json();

  if (!backendResponse.ok) {
    return NextResponse.json(data, { status: backendResponse.status });
  }

  // Only return the user object to the client — never the tokens themselves
  const response = NextResponse.json({ user: data.user });

  const cookieOptions = {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
  };

  response.cookies.set(ACCESS_TOKEN_COOKIE, data.access, {
    ...cookieOptions,
    maxAge: ACCESS_TOKEN_MAX_AGE,
  });
  response.cookies.set(REFRESH_TOKEN_COOKIE, data.refresh, {
    ...cookieOptions,
    maxAge: REFRESH_TOKEN_MAX_AGE,
  });

  return response;
}
