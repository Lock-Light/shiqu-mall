// Keep browser URLs inside this application's mount point (e.g. /dingping/).
export function appUrl(path = '') {
  const base = import.meta.env.BASE_URL
  if (/^(https?:|blob:|data:)/i.test(path)) return path
  if (base !== '/' && path.startsWith(base)) return path
  return base + String(path).replace(/^\/+/, '')
}
