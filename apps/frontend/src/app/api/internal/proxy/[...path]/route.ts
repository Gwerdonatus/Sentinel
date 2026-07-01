/**
 * ALL /api/internal/proxy/[...path]
 *
 * Generic proxy to the Django backend. Reads the access token from the
 * httpOnly cookie, attaches it as a Bearer header, and forwards the request.
 *
 * On a 401 from the backend (expired access token), attempts a single
 * silent refresh using the refresh token cookie, retries the original
 * request once, and updates the access token cookie on success.
 *
 * This means the dashboard never has to think about token expiry —
 * every request through this proxy either succeeds transparently or
 * the user is redirected to /login because the refresh token itself expired.
 */

import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_INTERNAL_URL ?? "http://backend:8000";

async function forwardRequest(
  request: NextRequest,
  path: string[],
  accessToken: string
): Promise<Response> {
  const targetPath = path.join("/");
  const search = request.nextUrl.search;
  const url = `${BACKEND_URL}/api/v1/${targetPath}/${search}`;

  const headers: Record<string, string> = {
    Authorization: `Bearer ${accessToken}`,
  };

  const contentType = request.headers.get("content-type");
  if (contentType) headers["Content-Type"] = contentType;

  const requestId = request.headers.get("x-request-id");
  if (requestId) headers["X-Request-ID"] = requestId;

  let body: string | undefined;
  if (request.method !== "GET" && request.method !== "HEAD") {
    body = await request.text();
  }

  return fetch(url, { method: request.method, headers, body });
}

async function refreshAccessToken(refreshToken: string): Promise<string | null> {
  const response = await fetch(`${BACKEND_URL}/api/v1/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: refreshToken }),
  });

  if (!response.ok) return null;
  const data = await response.json();
  return data.access as string;
}

async function handler(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  const { path } = await params;
  const accessToken = request.cookies.get("sentinel_access")?.value;
  const refreshToken = request.cookies.get("sentinel_refresh")?.value;

  if (!accessToken) {
    return NextResponse.json(
      { error: { code: "no_session", message: "Not authenticated." } },
      { status: 401 }
    );
  }

  let backendResponse = await forwardRequest(request, path, accessToken);

  // Silent refresh on expired access token
  if (backendResponse.status === 401 && refreshToken) {
    const newAccessToken = await refreshAccessToken(refreshToken);

    if (newAccessToken) {
      backendResponse = await forwardRequest(request, path, newAccessToken);

      const body = await backendResponse.text();
      const response = new NextResponse(body, {
        status: backendResponse.status,
        headers: { "Content-Type": backendResponse.headers.get("content-type") ?? "application/json" },
      });

      response.cookies.set("sentinel_access", newAccessToken, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
        maxAge: 15 * 60,
      });

      return response;
    }

    // Refresh failed — refresh token itself is expired/invalid
    const response = NextResponse.json(
      { error: { code: "session_expired", message: "Session expired. Please log in again." } },
      { status: 401 }
    );
    response.cookies.delete("sentinel_access");
    response.cookies.delete("sentinel_refresh");
    return response;
  }

  const body = await backendResponse.text();
  return new NextResponse(body, {
    status: backendResponse.status,
    headers: { "Content-Type": backendResponse.headers.get("content-type") ?? "application/json" },
  });
}

export {
  handler as GET,
  handler as POST,
  handler as PUT,
  handler as PATCH,
  handler as DELETE,
};
