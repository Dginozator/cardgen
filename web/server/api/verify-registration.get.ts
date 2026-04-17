import { verifyEmailRedirectResult } from "../../utils/verifyEmailRedirect";

/**
 * Серверный запрос к Directus: в браузере fetch+manual redirect часто не отдаёт Location
 * (opaqueredirect / абсолютный URL на другой host). Здесь заголовки читаются на Node.
 */
export default defineEventHandler(async (event) => {
  const q = getQuery(event);
  const raw = q.token;
  const token = Array.isArray(raw) ? raw[0] : raw;
  if (typeof token !== "string" || !token.trim()) {
    return { result: "invalid" as const };
  }

  const upstream = String(process.env.DIRECTUS_UPSTREAM || "").replace(
    /\/$/,
    "",
  );
  if (!upstream) {
    throw createError({
      statusCode: 503,
      statusMessage:
        "DIRECTUS_UPSTREAM is not set on the server (needed for email verification).",
    });
  }

  const url = `${upstream}/users/register/verify-email?token=${encodeURIComponent(token.trim())}`;
  const res = await fetch(url, {
    method: "GET",
    redirect: "manual",
  });

  const loc =
    res.headers.get("Location") || res.headers.get("location") || "";

  if ([301, 302, 303, 307, 308].includes(res.status)) {
    return { result: verifyEmailRedirectResult(loc) };
  }

  return { result: "error" as const };
});
