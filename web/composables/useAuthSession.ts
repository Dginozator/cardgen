type SessionUser = {
  id?: string;
  email?: string;
  first_name?: string;
  last_name?: string;
};

const TOKEN_KEY = "cardgen_auth_token";

export function useAuthSession() {
  const config = useRuntimeConfig();
  const token = useState<string>("auth:token", () => "");
  const user = useState<SessionUser | null>("auth:user", () => null);
  const checking = useState<boolean>("auth:checking", () => false);

  const isAuthenticated = computed(() => Boolean(token.value));

  function saveToken(nextToken: string) {
    token.value = nextToken;
    if (typeof window !== "undefined") {
      localStorage.setItem(TOKEN_KEY, nextToken);
    }
  }

  function loadToken() {
    if (typeof window === "undefined") return;
    const saved = localStorage.getItem(TOKEN_KEY) || "";
    if (saved) {
      token.value = saved;
    }
  }

  function clearSession() {
    token.value = "";
    user.value = null;
    if (typeof window !== "undefined") {
      localStorage.removeItem(TOKEN_KEY);
    }
  }

  async function checkSession() {
    if (!token.value) return false;
    checking.value = true;
    try {
      const me = await $fetch<{ data?: SessionUser }>(
        `${config.public.directusBase}/users/me`,
        {
          headers: {
            Authorization: `Bearer ${token.value}`,
          },
        }
      );
      user.value = me?.data || null;
      return true;
    } catch {
      clearSession();
      return false;
    } finally {
      checking.value = false;
    }
  }

  return {
    token,
    user,
    checking,
    isAuthenticated,
    saveToken,
    loadToken,
    clearSession,
    checkSession,
  };
}
