// In production, empty string means same-origin `/api/*` (proxied by app/api/[...path] to BACKEND_URL).
// Set NEXT_PUBLIC_BACKEND_URL only if you want the browser to call the backend URL directly (public https).
export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  (process.env.NODE_ENV === "production" ? "" : "http://localhost:8000");

export const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

export function apiHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...extra };
  if (API_KEY) {
    headers["X-API-Key"] = API_KEY;
  }
  return headers;
}
