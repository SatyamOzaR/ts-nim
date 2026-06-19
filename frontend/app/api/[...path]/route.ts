import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

function backendBase(): string | null {
  const b =
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    (process.env.NODE_ENV === "production" ? "" : "http://localhost:8000");
  if (!b) return null;
  return b.replace(/\/$/, "");
}

async function proxy(request: NextRequest, pathSegments: string[]) {
  const base = backendBase();
  if (!base) {
    return NextResponse.json(
      {
        detail:
          "BACKEND_URL (or NEXT_PUBLIC_BACKEND_URL) is not set on the frontend service.",
      },
      { status: 503 }
    );
  }
  const path = pathSegments.join("/");
  const url = new URL(request.url);
  const target = `${base}/api/${path}${url.search}`;

  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("connection");
  // Match backend API_KEY without baking NEXT_PUBLIC_API_KEY at build time.
  const serverKey = process.env.API_KEY;
  if (serverKey) {
    headers.set("X-API-Key", serverKey);
  }

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request.body;
    Object.assign(init, { duplex: "half" });
  }

  const resp = await fetch(target, init);
  const out = new NextResponse(resp.body, {
    status: resp.status,
    statusText: resp.statusText,
  });
  resp.headers.forEach((value, key) => {
    if (key.toLowerCase() === "transfer-encoding") return;
    out.headers.set(key, value);
  });
  return out;
}

function handler() {
  return async (
    request: NextRequest,
    context: { params: Promise<{ path: string[] }> }
  ) => {
    const { path } = await context.params;
    return proxy(request, path);
  };
}

export const GET = handler();
export const POST = handler();
export const PUT = handler();
export const PATCH = handler();
export const DELETE = handler();
export const OPTIONS = handler();
export const HEAD = handler();
