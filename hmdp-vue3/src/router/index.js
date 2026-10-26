import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores'
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  scrollBehavior(to, from, saved) {
    if (to.path !== '/index')
      return saved || (to.hash ? { el: to.hash, top: 24 } : { top: 0 })
    // The router owns history-entry positions. Wait until the async grid is laid out.
    return new Promise((resolve) => {
      const started = performance.now()
      function ready() {
        if (router.currentRoute.value.fullPath !== to.fullPath)
          return resolve(false)
        if (
          document.querySelector('#experiences[aria-busy="false"]') ||
          performance.now() - started > 5000
        ) {
          const filtered =
            to.query.q ||
            to.query.category ||
            Number(to.query.page || 1) > 1 ||
            to.query.sort
          resolve(
            saved ||
              (to.hash || filtered
                ? { el: to.hash || '#experiences', top: 24 }
                : { top: 0 })
          )
        } else requestAnimationFrame(ready)
      }
      requestAnimationFrame(ready)
    })
  },
  routes: [
    { path: '/', redirect: '/index' },
    { path: '/login', component: () => import('@/views/login/LoginPage.vue') },
    {
      path: '/register',
      redirect: (to) => ({ path: '/login', query: to.query })
    },
    {
      path: '/index',
      meta: { commerce: true },
      component: () => import('@/views/mall/MallHome.vue')
    },
    { path: '/discover', component: () => import('@/views/index.vue') },
    {
      path: '/places',
      meta: { commerce: true },
      component: () => import('@/views/mall/ReferencePlaces.vue')
    },
    {
      path: '/products/:id',
      meta: { commerce: true },
      component: () => import('@/views/mall/ProductDetail.vue')
    },
    {
      path: '/checkout/:sku',
      meta: { commerce: true, auth: true },
      component: () => import('@/views/mall/Checkout.vue')
    },
    {
      path: '/orders',
      meta: { commerce: true, auth: true },
      component: () => import('@/views/mall/Orders.vue')
    },
    {
      path: '/orders/:id',
      meta: { commerce: true, auth: true },
      component: () => import('@/views/mall/OrderDetail.vue')
    },
    {
      path: '/merchant',
      meta: { commerce: true, auth: true },
      component: () => import('@/views/mall/Merchant.vue')
    },
    { path: '/shopList', component: () => import('@/views/shop/ShopList.vue') },
    {
      path: '/shopDetail/:id',
      component: () => import('@/views/shop/ShopDetail.vue')
    },
    {
      path: '/blogDetail/:id',
      component: () => import('@/views/blog/BlogDetail.vue')
    },
    {
      path: '/blogEdit',
      meta: { auth: true },
      component: () => import('@/views/blog/BlogEdit.vue')
    },
    {
      path: '/InfoHtml',
      meta: { auth: true },
      component: () => import('@/views/info/InfoHtml.vue')
    },
    {
      path: '/InfoEdit',
      meta: { auth: true },
      component: () => import('@/views/info/InfoEdit.vue')
    },
    {
      path: '/InfoOther/:id',
      component: () => import('@/views/info/InfoOther.vue')
    },
    {
      path: '/:pathMatch(.*)*',
      component: () => import('@/views/NotFound.vue')
    }
  ]
})
router.beforeEach((to) => {
  if (to.meta.auth && !useUserStore().token)
    return { path: '/login', query: { redirect: to.fullPath } }
})
const titles = {
  '/index': '发现身边的好体验',
  '/discover': '体验分享',
  '/places': '开放场所参考',
  '/login': '登录',
  '/orders': '我的订单',
  '/merchant': '商户工作台',
  '/shopList': '附近门店',
  '/InfoHtml': '个人中心',
  '/InfoEdit': '编辑资料',
  '/blogEdit': '发布体验分享'
}
router.afterEach((to) => {
  const title =
    titles[to.path] ||
    (to.path.startsWith('/products/')
      ? '体验详情'
      : to.path.startsWith('/checkout/')
        ? '确认订单'
        : to.path.startsWith('/orders/')
          ? '订单详情'
          : to.path.startsWith('/shopDetail/')
            ? '门店详情'
            : to.path.startsWith('/blogDetail/')
              ? '分享详情'
              : to.path.startsWith('/InfoOther/')
                ? '作者主页'
                : '页面未找到')
  document.title = to.path === '/index' ? '拾趣｜' + title : title + '｜拾趣'
})
export default router
