import { NextResponse } from "next/server";
/** Exposes the development backend schema on the frontend origin. No credentials are forwarded. */
export async function GET() {
  try {
    const response = await fetch(
      `${process.env.BACKEND_INTERNAL_URL ?? "http://backend:8000"}/api/schema/?format=json`,
      { cache: "no-store", signal: AbortSignal.timeout(5000) },
    );
    if (!response.ok)
      return NextResponse.json(
        { error: "The API schema is unavailable in this environment." },
        { status: response.status },
      );
    return new NextResponse(await response.text(), {
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return NextResponse.json(
      { error: "The backend is currently unavailable. Try again shortly." },
      { status: 503 },
    );
  }
}
