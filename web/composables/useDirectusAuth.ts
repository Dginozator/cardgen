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

  function registrationVerificationUrl(): string {
    const configured = (
      config.public.directusVerifyUrl as string | undefined
    )?.trim();
    if (configured) {
      return configured.replace(/\/$/, "");
    }
    if (typeof window !== "undefined" && window.location?.origin) {
      return `${window.location.origin}/verify-email`;
    }
    return "http://localhost:8080/verify-email";
  }

  async function register(email: string, password: string) {
    try {
      return await $fetch(`${base}/users/register`, {
        method: "POST",
        body: {
          email,
          password,
          verification_url: registrationVerificationUrl(),
        },
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
   * Проверка через GET /api/verify-registration на Nitro: там читается Location от Directus
   * (в браузере при redirect:manual заголовок часто недоступен).
   */
  async function verifyRegistrationEmail(token: string): Promise<
    "success" | "invalid" | "error"
  > {
    if (!token?.trim()) {
      return "invalid";
    }
    try {
      const data = await $fetch<{ result: "success" | "invalid" | "error" }>(
        "/api/verify-registration",
        {
          query: { token: token.trim() },
        },
      );
      return data.result ?? "error";
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
