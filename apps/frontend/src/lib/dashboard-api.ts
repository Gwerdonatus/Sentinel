type QueryValue = string | number | boolean | null | undefined;

interface RequestOptions {
  params?: Record<string, QueryValue>;
}

interface ApiErrorBody {
  detail?: string;
  error?: string | { message?: string };
  message?: string;
}

export class DashboardApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly body: unknown
  ) {
    super(message);
    this.name = "DashboardApiError";
  }
}

function buildUrl(path: string, params?: Record<string, QueryValue>): string {
  const normalizedPath = path.replace(/^\/+|\/+$/g, "");
  const query = new URLSearchParams();

  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== null && value !== undefined && value !== "") {
      query.set(key, String(value));
    }
  }

  const queryString = query.toString();
  return `/api/internal/proxy/${normalizedPath}${queryString ? `?${queryString}` : ""}`;
}

function errorMessage(body: unknown, status: number): string {
  if (typeof body !== "object" || body === null) {
    return `Request failed with status ${status}.`;
  }

  const value = body as ApiErrorBody;
  if (typeof value.detail === "string") return value.detail;
  if (typeof value.message === "string") return value.message;
  if (typeof value.error === "string") return value.error;
  if (typeof value.error === "object" && typeof value.error?.message === "string") {
    return value.error.message;
  }
  return `Request failed with status ${status}.`;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options?: RequestOptions
): Promise<T> {
  const response = await fetch(buildUrl(path, options?.params), {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text) as unknown;
    } catch {
      payload = text;
    }
  }

  if (!response.ok) {
    throw new DashboardApiError(errorMessage(payload, response.status), response.status, payload);
  }

  return payload as T;
}

export const dashboardApi = {
  get<T>(path: string, options?: RequestOptions): Promise<T> {
    return request<T>("GET", path, undefined, options);
  },
  post<T>(path: string, body?: unknown): Promise<T> {
    return request<T>("POST", path, body);
  },
  put<T>(path: string, body?: unknown): Promise<T> {
    return request<T>("PUT", path, body);
  },
  patch<T>(path: string, body?: unknown): Promise<T> {
    return request<T>("PATCH", path, body);
  },
  delete(path: string): Promise<void> {
    return request<void>("DELETE", path);
  },
};
