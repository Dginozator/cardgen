/** Pathname из заголовка Location (абсолютный URL или относительный путь). */
export function pathnameFromRedirectLocation(locationHeader: string): string {
  const raw = locationHeader.trim();
  if (!raw) return "";
  if (/^[a-z][a-z0-9+.-]*:/i.test(raw)) {
    try {
      return new URL(raw).pathname;
    } catch {
      return "";
    }
  }
  return raw.split(/[?#]/, 1)[0] || "";
}

/**
 * Успешная верификация: Location ведёт на /admin/users/:id
 * (см. Directus GET /users/register/verify-email → 302).
 */
export function verifyEmailRedirectResult(locationHeader: string):
  | "success"
  | "invalid"
  | "error" {
  const loc = locationHeader.trim();
  if (!loc) return "error";

  const pathOnly = pathnameFromRedirectLocation(loc);
  const p = pathOnly.startsWith("/") ? pathOnly : `/${pathOnly}`;

  if (/\/admin\/users\/[^/\s?#]+/.test(p)) {
    return "success";
  }

  const pl = p.toLowerCase();
  if (
    pl.includes("/admin/login") ||
    /\/login(?:\/|\?|#|$)/.test(pl)
  ) {
    return "invalid";
  }
  return "error";
}
