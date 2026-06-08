type SessionUser = {
  id?: string;
  email?: string;
  first_name?: string;
  last_name?: string;
};

const TOKEN_KEY = "cardgen_auth_token";
const REFRESH_TOKEN_KEY = "cardgen_refresh_token";
const TOKEN_EXPIRES_KEY = "cardgen_token_expires";

export function useAuthSession() {
  const config = useRuntimeConfig();
  const token = useState<string>("auth:token", () => "");
  const refreshToken = useState<string>("auth:refreshToken", () => "");
  const user = useState<SessionUser | null>("auth:user", () => null);
  const checking = useState<boolean>("auth:checking", () => false);
  const tokenExpiresAt = useState<number>("auth:expiresAt", () => 0);

  const isAuthenticated = computed(() => Boolean(token.value));

  function saveToken(
    nextToken: string,
    nextRefreshToken?: string,
    expiresInSeconds?: number,
  ) {
    token.value = nextToken;
    if (typeof window !== "undefined") {
      localStorage.setItem(TOKEN_KEY, nextToken);
      if (nextRefreshToken) {
        refreshToken.value = nextRefreshToken;
        localStorage.setItem(REFRESH_TOKEN_KEY, nextRefreshToken);
      }
      if (expiresInSeconds) {
        const at = Date.now() + expiresInSeconds * 1000;
        tokenExpiresAt.value = at;
        localStorage.setItem(TOKEN_EXPIRES_KEY, String(at));
      }
    }
  }

  function loadToken() {
    if (typeof window === "undefined") return;
    const saved = localStorage.getItem(TOKEN_KEY) || "";
    if (saved) {
      token.value = saved;
    }
    const savedRefresh = localStorage.getItem(REFRESH_TOKEN_KEY) || "";
    if (savedRefresh) {
      refreshToken.value = savedRefresh;
    }
    const savedExpires = localStorage.getItem(TOKEN_EXPIRES_KEY) || "";
    if (savedExpires) {
      tokenExpiresAt.value = Number(savedExpires);
    }
  }

  function clearSession() {
    token.value = "";
    refreshToken.value = "";
    user.value = null;
    tokenExpiresAt.value = 0;
    if (typeof window !== "undefined") {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(REFRESH_TOKEN_KEY);
      localStorage.removeItem(TOKEN_EXPIRES_KEY);
    }
  }

  /** Whether the access token is expired (30 s buffer). */
  function isTokenExpired(): boolean {
    if (!tokenExpiresAt.value) return false;
    return Date.now() > tokenExpiresAt.value - 30_000;
  }

  /** Exchange the stored refresh token for a new access token. */
  async function tryRefresh(): Promise<boolean> {
    if (!refreshToken.value) return false;
    try {
      const resp = await $fetch<{
        data?: {
          access_token?: string;
          refresh_token?: string;
          expires?: number;
        };
      }>(`${config.public.directusBase}/auth/refresh`, {
        method: "POST",
        body: { refresh_token: refreshToken.value },
      });
      const d = resp?.data;
      if (d?.access_token) {
        saveToken(d.access_token, d.refresh_token, d.expires);
        return true;
      }
      return false;
    } catch {
      clearSession();
      return false;
    }
  }

  /** Make sure the access token is still valid, refreshing proactively. */
  async function ensureFreshToken(): Promise<boolean> {
    if (!token.value) return false;
    if (!isTokenExpired()) return true;
    return tryRefresh();
  }

  async function checkSession() {
    if (!token.value) return false;
    checking.value = true;
    try {
      if (isTokenExpired() && refreshToken.value) {
        const ok = await tryRefresh();
        if (!ok) return false;
      }
      const me = await $fetch<{ data?: SessionUser }>(
        `${config.public.directusBase}/users/me`,
        {
          headers: { Authorization: `Bearer ${token.value}` },
        },
      );
      user.value = me?.data || null;
      return true;
    } catch {
      if (refreshToken.value) {
        const ok = await tryRefresh();
        if (!ok) return false;
        try {
          const me = await $fetch<{ data?: SessionUser }>(
            `${config.public.directusBase}/users/me`,
            {
              headers: { Authorization: `Bearer ${token.value}` },
            },
          );
          user.value = me?.data || null;
          return true;
        } catch {
          return false;
        }
      }
      return false;
    } finally {
      checking.value = false;
    }
  }

  return {
    token,
    refreshToken,
    user,
    checking,
    isAuthenticated,
    saveToken,
    loadToken,
    clearSession,
    checkSession,
    tryRefresh,
    ensureFreshToken,
  };
}