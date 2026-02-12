export function resolveImageUrl(url?: string | null): string | null {
  if (!url) return null;
  const raw = url.trim();
  if (!raw) return null;

  if (raw.startsWith("/static/images/")) return raw;
  if (raw.startsWith("static/images/")) return `/${raw}`;
  if (raw.startsWith("data:image")) return raw;

  if (raw.includes("/static/images/")) {
    return raw.slice(raw.indexOf("/static/images/"));
  }
  if (raw.startsWith("data/images/")) {
    const filename = raw.split("/").pop();
    return filename ? `/static/images/${filename}` : raw;
  }
  return raw;
}
