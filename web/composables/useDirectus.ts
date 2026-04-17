type DirectusUser = {
  id: string;
  email?: string | null;
  first_name?: string | null;
  last_name?: string | null;
};

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
      return errors[0].message as string;
    }
  }
  if (typeof body === "string" && body.trim()) return body;
  return fallback;
}

/**
 * Мелкие операции над текущим Directus-аккаунтом, которых нет в
 * `useDirectusAuth` / `useAuthSession`. Токен берём из `useAuthSession`,
 * чтобы не плодить второй механизм входа.
 */
export function useDirectus() {
  const config = useRuntimeConfig();
  const session = useAuthSession();
  const base = (config.public.directusBase as string) || "/api/d";

  async function request<T = unknown>(
    path: string,
    init: RequestInit = {},
  ): Promise<T> {
    const headers = new Headers(init.headers || {});
    if (!headers.has("Content-Type") && init.body && !(init.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
    }
    if (session.token.value) {
      headers.set("Authorization", `Bearer ${session.token.value}`);
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

  async function getMe(): Promise<DirectusUser> {
    return request<DirectusUser>(
      "/users/me?fields=id,email,first_name,last_name",
      { method: "GET" },
    );
  }

  async function deleteAccount(): Promise<void> {
    const me = await getMe();
    await request<null>(`/users/${encodeURIComponent(me.id)}`, { method: "DELETE" });
    session.clearSession();
  }

  return { getMe, deleteAccount };
}

export type { DirectusUser };
