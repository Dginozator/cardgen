const TOKEN_KEY = "cardgen_directus_token";
const REFRESH_KEY = "cardgen_directus_refresh";

type DirectusUser = {
  id: string;
  email: string | null;
  first_name?: string | null;
  last_name?: string | null;
};

type LoginResult = {
  access_token: string;
  refresh_token?: string | null;
  expires?: number | null;
};

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

function readToken(): string | null {
  if (!isBrowser()) return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

function writeTokens(access: string | null, refresh?: string | null): void {
  if (!isBrowser()) return;
  if (access) {
    window.localStorage.setItem(TOKEN_KEY, access);
  } else {
    window.localStorage.removeItem(TOKEN_KEY);
  }
  if (refresh === undefined) return;
  if (refresh) {
    window.localStorage.setItem(REFRESH_KEY, refresh);
  } else {
    window.localStorage.removeItem(REFRESH_KEY);
  }
}

async function parseJsonSafe(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function extractError(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "errors" in body) {
    const errors = (body as { errors?: Array<{ message?: string }> }).errors;
    if (Array.isArray(errors) && errors.length && errors[0]?.message) {
      return errors[0].message;
    }
  }
  if (typeof body === "string" && body.trim()) return body;
  return fallback;
}

export function useDirectus() {
  const config = useRuntimeConfig();
  const base = (config.public.directusBase as string) || "/api/d";

  async function request<T = unknown>(
    path: string,
    init: RequestInit = {},
    { auth = true }: { auth?: boolean } = {},
  ): Promise<T> {
    const headers = new Headers(init.headers || {});
    if (!headers.has("Content-Type") && init.body && !(init.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }
    if (auth) {
      const token = readToken();
      if (token) headers.set("Authorization", `Bearer ${token}`);
    }
    const url = `${base}${path.startsWith("/") ? path : `/${path}`}`;
    const res = await fetch(url, { ...init, headers });
    const body = await parseJsonSafe(res);
    if (!res.ok) {
      throw new Error(extractError(body, `HTTP ${res.status}`));
    }
    if (body && typeof body === "object" && "data" in body) {
      return (body as { data: T }).data;
    }
    return body as T;
  }

  async function login(email: string, password: string): Promise<void> {
    const data = await request<LoginResult>(
      "/auth/login",
      {
        method: "POST",
        body: JSON.stringify({ email, password }),
      },
      { auth: false },
    );
    if (!data?.access_token) {
      throw new Error("Сервер не вернул токен доступа.");
    }
    writeTokens(data.access_token, data.refresh_token ?? null);
  }

  async function logout(): Promise<void> {
    const refresh = isBrowser() ? window.localStorage.getItem(REFRESH_KEY) : null;
    writeTokens(null, null);
    if (!refresh) return;
    try {
      await request(
        "/auth/logout",
        {
          method: "POST",
          body: JSON.stringify({ refresh_token: refresh }),
        },
        { auth: false },
      );
    } catch {
      // локальный токен уже удалён — выходим тихо
    }
  }

  async function getMe(): Promise<DirectusUser> {
    return request<DirectusUser>(
      "/users/me?fields=id,email,first_name,last_name",
      { method: "GET" },
    );
  }

  async function deleteAccount(): Promise<void> {
    const me = await getMe();
    await request<null>(`/users/${encodeURIComponent(me.id)}`, { method: "DELETE" });
    writeTokens(null, null);
  }

  function isAuthenticated(): boolean {
    return Boolean(readToken());
  }

  return { login, logout, getMe, deleteAccount, isAuthenticated };
}

export type { DirectusUser };
