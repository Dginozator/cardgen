/**
 * Успех: редирект на пользователя в админке Directus (/admin/users/:id).
 * Проверяем всю строку Location (относительный путь или полный URL).
 */
export function verifyEmailRedirectResult(locationHeader: string):
  | "success"
  | "invalid"
  | "error" {
  const loc = locationHeader
    .trim()
    .replace(/^["']+|["']+$/g, "");
  if (!loc) return "error";

  if (/\/admin\/users\/[^/\s?#]+/.test(loc)) {
    return "success";
  }

  const low = loc.toLowerCase();
  if (low.includes("/admin/login") || /\/login(?:\/|\?|#|$)/.test(low)) {
    return "invalid";
  }
  return "error";
}
