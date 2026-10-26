import axios from 'axios'
import JSONbig from 'json-bigint'
import { useUserStore } from '@/stores'
import router from '@/router'
import { appUrl } from './publicPath'
const request = axios.create({
  baseURL: appUrl('api'),
  timeout: 12000,
  transformResponse: [
    (data) => {
      try {
        return JSONbig({ storeAsString: true }).parse(data)
      } catch {
        return data
      }
    }
  ]
})
request.interceptors.request.use((config) => {
  const token = useUserStore().token
  if (token) config.headers.Authorization = token
  return config
})
request.interceptors.response.use(
  (response) => {
    const body = response.data
    if (!body || typeof body.success !== 'boolean')
      throw new Error('服务响应异常，请重试')
    if (!body.success) throw new Error(body.errorMsg || '操作未完成，请重试')
    return body
  },
  (cause) => {
    const status = cause.response?.status,
      error = new Error(
        cause.response?.data?.errorMsg ||
          (status === 413
            ? '图片不能超过5MB'
            : cause.code === 'ECONNABORTED'
              ? '请求超时，请重试'
              : '网络或服务暂不可用，请重试')
      )
    if (status === 401) {
      error.auth = true
      error.message = '登录已过期，请重新登录'
      useUserStore().clear()
      if (
        !cause.config.optionalAuth &&
        router.currentRoute.value.path !== '/login'
      )
        router.replace({
          path: '/login',
          query: { redirect: router.currentRoute.value.fullPath }
        })
    }
    error.status = status
    return Promise.reject(error)
  }
)
export default request
export const baseURL = appUrl('api')
