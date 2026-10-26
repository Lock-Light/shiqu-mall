import { ElMessage } from 'element-plus'
import request from './request'
import router from '@/router'
import { useUserStore } from '@/stores'
import { appUrl } from './publicPath'
export function text(value) {
  return String(value ?? '')
    .replace(/<br\s*\/?\s*>/gi, '\n')
    .replace(/\\r\\n|\\n|\\r/g, '\n')
    .replace(/\r\n?/g, '\n')
    .replace(
      /&(nbsp|amp|lt|gt|quot|apos|#39);/g,
      (_, key) =>
        ({
          nbsp: ' ',
          amp: '&',
          lt: '<',
          gt: '>',
          quot: '"',
          apos: "'",
          '#39': "'"
        })[key]
    )
}
export function imagePath(value) {
  let src = String(value || '')
  const base = import.meta.env.BASE_URL
  if (base !== '/' && src.startsWith(base)) src = '/' + src.slice(base.length)
  src = src.replace(/^\/?src\/assets/, '')
  if (!src) return '/imgs/icons/default-icon.png'
  if (/^(https?:|blob:|data:)/i.test(src)) return src
  if (src.startsWith('/imgs/')) return src
  return '/imgs/' + src.replace(/^\//, '')
}
export function image(value) {
  return appUrl(imagePath(value))
}
export function images(value) {
  return (Array.isArray(value) ? value : String(value || '').split(','))
    .filter(Boolean)
    .map(image)
}
export function fallback(event) {
  // Element Plus owns its image loading/error state and error slot. Replacing
  // its inner DOM src here can turn a fallback load into a retry of the failed URL.
  if (event.target?.tagName !== 'IMG' || event.target.closest('.el-image'))
    return
  if (event.target.dataset.fallback) return
  event.target.dataset.fallback = '1'
  event.target.src = appUrl('imgs/icons/default-icon.png')
}
// Plus stores display amounts in yuan; preserve the upstream API unit.
export function money(value) {
  return value !== null &&
    value !== undefined &&
    value !== '' &&
    Number.isFinite(Number(value))
    ? Number(value).toFixed(2)
    : '—'
}
export function date(value) {
  const d = new Date(String(value || '').replace(' ', 'T'))
  return Number.isNaN(d.getTime())
    ? ''
    : d.toLocaleString('zh-CN', { hour12: false })
}
export function merge(rows, more) {
  const map = new Map(rows.map((r) => [String(r.id), r]))
  more.forEach((r) => map.set(String(r.id), r))
  return [...map.values()]
}
export function ensureLogin() {
  if (useUserStore().token) return true
  router.push({
    path: '/login',
    query: { redirect: router.currentRoute.value.fullPath }
  })
  return false
}
export function notify(error) {
  if (!error?.auth) ElMessage.error(error?.message || '操作失败，请重试')
}
export async function me(optional = false) {
  if (!useUserStore().token)
    return optional ? null : Promise.reject(new Error('请先登录'))
  try {
    return (await request.get('/user/me', { optionalAuth: optional })).data
  } catch (e) {
    if (optional && e.auth) return null
    throw e
  }
}
export async function like(blog) {
  if (!ensureLogin() || blog.busy) return
  blog.busy = true
  try {
    await request.put('/blog/like/' + blog.id)
    Object.assign(blog, (await request.get('/blog/' + blog.id)).data)
  } catch (e) {
    notify(e)
  } finally {
    blog.busy = false
  }
}
export async function upload(file) {
  if (!file) throw new Error('请选择图片')
  if (!/\.(png|jpe?g|webp)$/i.test(file.name))
    throw new Error('请选择JPG、PNG或WebP图片')
  if (file.size > 5 * 1024 * 1024) throw new Error('图片不能超过5MB')
  const form = new FormData()
  form.append('file', file)
  // Store a canonical media path; the deployment prefix belongs only in the UI.
  return imagePath((await request.post('/upload/blog', form)).data)
}
export async function share() {
  try {
    await navigator.clipboard.writeText(location.href)
    ElMessage.success('链接已复制')
  } catch {
    ElMessage.info(location.href)
  }
}
