type ApiError = {
  message: string;
  raw?: unknown;
};

type LoginResponse = {
  data?: {
    access_token?: string;
    refresh_token?: string;
    expires?: number;
  };
};

function parseError(error: unknown): ApiError {
  const fallback = "Не удалось выполнить запрос. Попробуйте позже.";
  if (error && typeof error === "object") {
    const maybe = error as {
      data?: { errors?: Array<{ message?: string }> };
      message?: string;
    };
    const apiMessage = maybe.data?.errors?.[0]?.message;
    if (apiMessage) {
      return { message: apiMessage, raw: error };
    }
    if (maybe.message) {
      return { message: maybe.message, raw: error };
    }
  }
  return { message: fallback, raw: error };
}

export function useDirectusAuth() {
  const config = useRuntimeConfig();
  const base = config.public.directusBase;
  const redirectUrl =
    config.public.directusResetUrl ||
    (typeof window !== "undefined"
      ? `${window.location.origin}/reset-password`
      : "/reset-password");

  async function register(email: string, password: string) {
    try {
      const verifyUrl = (config.public.directusVerifyUrl as string)?.trim();
      const body: Record<string, string> = { email, password };
      // Иначе Directus проверяет URL по USER_REGISTER_URL_ALLOW_LIST и отдаёт 400.
      if (verifyUrl) {
        body.verification_url = verifyUrl.replace(/\/$/, "");
      }
      return await $fetch(`${base}/users/register`, {
        method: "POST",
        body,
      });
    } catch (error) {
      throw parseError(error);
    }
  }

  async function login(email: string, password: string) {
    try {
      return await $fetch<LoginResponse>(`${base}/auth/login`, {
        method: "POST",
        body: { email, password, mode: "json" },
      });
    } catch (error) {
      throw parseError(error);
    }
  }

  async function requestPasswordReset(email: string) {
    try {
      return await $fetch(`${base}/auth/password/request`, {
        method: "POST",
        body: {
          email,
          reset_url: redirectUrl,
        },
      });
    } catch (error) {
      throw parseError(error);
    }
  }

  async function resetPassword(token: string, password: string) {
    try {
      return await $fetch(`${base}/auth/password/reset`, {
        method: "POST",
        body: { token, password },
      });
    } catch (error) {
      throw parseError(error);
    }
  }

  /**
   * Directus отвечает на GET /users/register/verify-email редиректом 302 на /admin/users/:id.
   * Не следуем редиректу — остаёмся в Nuxt и интерпретируем Location.
   */
  async function verifyRegistrationEmail(token: string): Promise<
    "success" | "invalid" | "error"
  > {
    if (!token?.trim()) {
      return "invalid";
    }
    try {
      const url = `${base}/users/register/verify-email?token=${encodeURIComponent(token.trim())}`;
      const res = await fetch(url, {
        method: "GET",
        redirect: "manual",
        credentials: "omit",
      });
      if ([301, 302, 303, 307, 308].includes(res.status)) {
        const loc = res.headers.get("Location") || "";
        if (loc.includes("/admin/users/")) {
          return "success";
        }
        if (loc.includes("/admin/login") || loc.toLowerCase().includes("login")) {
          return "invalid";
        }
        return "error";
      }
      return "error";
    } catch {
      return "error";
    }
  }

  return {
    register,
    login,
    requestPasswordReset,
    resetPassword,
    verifyRegistrationEmail,
  };
}
