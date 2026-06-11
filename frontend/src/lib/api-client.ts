/**
 * QuantLab Safe API Client
 * 
 * Wraps all backend communication with:
 * - Safe JSON parsing (never crashes on HTML error pages)
 * - Structured error responses { ok, data, error, status }
 * - Network failure handling
 * - Per-request timeout support
 * - Content-Type validation
 */

const API_BASE = "/api";
const DEFAULT_TIMEOUT = 120000; // 2 minutes (forge endpoints can take 60-120s)

export interface ApiResult<T = any> {
  ok: boolean;
  status: number;
  data: T | null;
  error: string | null;
  isJsonError: boolean; // true when server returned non-JSON (usually 500 HTML page)
  isNetworkError: boolean;
}

/**
 * Safely parse a Response as JSON. If the body is not valid JSON
 * (e.g. an HTML error page), return a structured error instead of throwing.
 */
async function safeJsonParse(res: Response): Promise<{ data: any | null; isJsonError: boolean }> {
  const contentType = res.headers.get("content-type") || "";
  
  // If content-type is clearly not JSON, don't even try to parse
  if (!contentType.includes("application/json") && res.status >= 400) {
    const text = await res.text().catch(() => "Unknown error");
    return {
      data: null,
      isJsonError: true,
    };
  }

  // Try to parse as JSON anyway (some endpoints return JSON without proper header)
  const text = await res.text().catch(() => "");
  
  if (!text.trim()) {
    return { data: null, isJsonError: false };
  }

  // Quick heuristic: if it starts with HTML, it's not JSON
  const firstChar = text.trim()[0];
  if (firstChar === "<" || firstChar === "I" || firstChar === "D") { // <html..., Internal Server..., DOCTYPE...
    return { data: null, isJsonError: true };
  }

  try {
    const data = JSON.parse(text);
    return { data, isJsonError: false };
  } catch {
    return { data: null, isJsonError: true };
  }
}

/**
 * Make a safe fetch request to the backend.
 * Never throws. Always returns an ApiResult.
 */
export async function apiFetch<T = any>(
  endpoint: string,
  options?: RequestInit & { timeout?: number }
): Promise<ApiResult<T>> {
  const url = endpoint.startsWith("http") ? endpoint : `${API_BASE}${endpoint}`;
  const timeout = options?.timeout || DEFAULT_TIMEOUT;

  // Create abort controller for timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const res = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    const { data, isJsonError } = await safeJsonParse(res);

    if (isJsonError) {
      return {
        ok: false,
        status: res.status,
        data: null,
        error: `Server returned an invalid response (status ${res.status}). The backend may be experiencing an error.`,
        isJsonError: true,
        isNetworkError: false,
      };
    }

    if (!res.ok) {
      // Backend returned a valid JSON error response
      const errorMsg =
        data?.detail ||
        data?.message ||
        data?.error ||
        `Request failed with status ${res.status}`;
      return {
        ok: false,
        status: res.status,
        data: null,
        error: errorMsg,
        isJsonError: false,
        isNetworkError: false,
      };
    }

    return {
      ok: true,
      status: res.status,
      data,
      error: null,
      isJsonError: false,
      isNetworkError: false,
    };
  } catch (err: any) {
    clearTimeout(timeoutId);

    if (err.name === "AbortError") {
      return {
        ok: false,
        status: 0,
        data: null,
        error: `Request timed out after ${timeout / 1000}s. The backend may be overloaded or offline.`,
        isJsonError: false,
        isNetworkError: true,
      };
    }

    return {
      ok: false,
      status: 0,
      data: null,
      error: err?.message || "Network error. Is the backend server running?",
      isJsonError: false,
      isNetworkError: true,
    };
  }
}

/**
 * Convenience wrappers for common HTTP methods
 */
export const api = {
  get: <T = any>(endpoint: string, options?: RequestInit & { timeout?: number }) =>
    apiFetch<T>(endpoint, { ...options, method: "GET" }),

  post: <T = any>(endpoint: string, body: any, options?: RequestInit & { timeout?: number }) =>
    apiFetch<T>(endpoint, {
      ...options,
      method: "POST",
      headers: { "Content-Type": "application/json", ...options?.headers },
      body: JSON.stringify(body),
    }),

  put: <T = any>(endpoint: string, body: any, options?: RequestInit & { timeout?: number }) =>
    apiFetch<T>(endpoint, {
      ...options,
      method: "PUT",
      headers: { "Content-Type": "application/json", ...options?.headers },
      body: JSON.stringify(body),
    }),

  delete: <T = any>(endpoint: string, options?: RequestInit & { timeout?: number }) =>
    apiFetch<T>(endpoint, { ...options, method: "DELETE" }),
};

/**
 * Human-friendly error message formatter
 */
export function formatApiError(result: ApiResult, context?: string): string {
  const prefix = context ? `${context}: ` : "";
  if (result.isNetworkError) {
    return `${prefix}Connection failed — ${result.error}`;
  }
  if (result.isJsonError) {
    return `${prefix}Backend error — ${result.error}`;
  }
  return `${prefix}${result.error}`;
}
