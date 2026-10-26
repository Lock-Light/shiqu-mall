import request from './request'
export const api = async (path, method = 'get', body) =>
  (await request({ url: path, method, data: body })).data
export function requestKey() {
  if (globalThis.crypto?.randomUUID) return crypto.randomUUID()
  // IP + HTTP is not a secure context: randomUUID is unavailable there.
  // getRandomValues still supplies cryptographic randomness for idempotency keys.
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 15) | 64
  bytes[8] = (bytes[8] & 63) | 128
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}
export const labels = {
  WAIT_PAY: '待付款',
  PAID: '待使用',
  USED: '已完成',
  CLOSED: '已关闭',
  EXPIRED: '已过期'
}
export const yuan = (v) => Number(v || 0).toFixed(2)
export function serverMillis(value) {
  const v = String(value || '').replace(' ', 'T')
  return Date.parse(/Z$|[+-]\d\d:\d\d$/.test(v) ? v : v + '+08:00')
}
export const dateLabel = (v) =>
  v ? new Date(serverMillis(v)).toLocaleString('zh-CN', { hour12: false }) : '—'
