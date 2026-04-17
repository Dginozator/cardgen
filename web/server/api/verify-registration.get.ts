import { getHeader, getRequestURL, type H3Event } from "h3";
import { verifyEmailRedirectResult } from "../../utils/verifyEmailRedirect";

/**
 * Публичный origin для fallback без DIRECTUS_UPSTREAM (запрос на тот же /api/d, что видит браузер).
 */
function buildPublicOrigin(event: H3Event): string | null {
  const xfProto = getHeader(event, "x-forwarded-proto")?.split(",")[0]?.trim();
  const xfHost = getHeader(event, "x-forwarded-host")?.split(",")[0]?.trim();
  const hostHeader = getHeader(event, "host")?.split(",")[0]?.trim();
  const host = xfHost || hostHeader;
  if (host && xfProto) {
    return `${xfProto}://${host}`;
  }
  try {
    return getRequestURL(event).origin;
  } catch {
    return null;
  }
}

export default defineEventHandler(async (event) => {
  const q = getQuery(event);
  const raw = q.token;
  const token = Array.isArray(raw) ? raw[0] : raw;
  if (typeof token !== "string" || !token.trim()) {
    return { result: "invalid" as const };
  }

  const encoded = encodeURIComponent(token.trim());

  const upstream = String(process.env.DIRECTUS_UPSTREAM || "").replace(
    /\/$/,
    "",
  );

  const directusPrefix = String(
    process.env.NUXT_PUBLIC_DIRECTUS_BASE || "/api/d",
  ).replace(/\/$/, "");

  let verifyUrl: string | null = null;

  if (upstream) {
    verifyUrl = `${upstream}/users/register/verify-email?token=${encoded}`;
  } else {
    const origin = buildPublicOrigin(event);
    if (origin) {
      verifyUrl = `${origin}${directusPrefix}/users/register/verify-email?token=${encoded}`;
    }
  }

  if (!verifyUrl) {
    throw createError({
      statusCode: 503,
      statusMessage:
        "Cannot resolve URL for email verification (set DIRECTUS_UPSTREAM or proxy headers).",
    });
  }

  const res = await fetch(verifyUrl, {
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
