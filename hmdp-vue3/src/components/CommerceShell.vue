<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores'
import { api } from '@/utils/commerce'
import UiIcon from './UiIcon.vue'
import { appUrl } from '@/utils/publicPath'
const route = useRoute(),
  router = useRouter(),
  store = useUserStore()
const roles = ref([]),
  search = ref('')
const links = [
  { name: '商城', title: '体验商城', path: '/index', icon: 'home' },
  {
    name: '附近',
    title: '附近门店',
    path: '/shopList?type=21',
    icon: 'nearby'
  },
  { name: '发现', title: '体验分享', path: '/discover', icon: 'discover' },
  { name: '我的', title: '个人中心', path: '/InfoHtml', icon: 'user' }
]
function active(path) {
  if (path === '/index')
    return (
      route.path === '/index' ||
      route.path.startsWith('/products/') ||
      route.path.startsWith('/checkout/')
    )
  if (path.startsWith('/shopList'))
    return route.path.startsWith('/shop') || route.path === '/places'
  if (path === '/discover')
    return route.path.startsWith('/blog') || route.path === '/discover'
  return route.path.startsWith('/Info') || route.path.startsWith('/orders')
}
watch(
  () => route.fullPath,
  () => {
    search.value = route.path === '/index' ? String(route.query.q || '') : ''
  },
  { immediate: true }
)
watch(
  () => store.token,
  async (token) => {
    roles.value = []
    if (!token) return
    try {
      const result = await api('/mall/me')
      if (store.token === token) roles.value = result.memberships || []
    } catch {
      /* Public navigation remains available. */
    }
  },
  { immediate: true }
)
function fallback(event) {
  const img = event.target
  if (img.tagName !== 'IMG' || img.closest('.el-image') || img.dataset.fallback)
    return
  img.dataset.fallback = '1'
  img.src = appUrl('brand/image-placeholder.svg')
}
function find() {
  router.push({
    path: '/index',
    query: { q: search.value.trim(), page: 1 },
    hash: '#experiences'
  })
}
</script>
<template>
  <div
    class="commerce"
    @error.capture="fallback"
    :class="{
      'is-home': route.path === '/index',
      'is-merchant': route.path === '/merchant'
    }"
  >
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <header class="commerce-header">
      <RouterLink to="/index" class="commerce-brand" aria-label="拾趣首页"
        ><img src="/brand/shiqu-mark.svg" width="36" height="36" alt="" /><span
          >拾趣</span
        ></RouterLink
      >
      <nav class="desktop-navigation" aria-label="商城导航">
        <RouterLink
          v-for="link in links.slice(0, 3)"
          :key="link.path"
          :to="link.path"
          :class="{ current: active(link.path) }"
          :aria-current="active(link.path) ? 'page' : undefined"
          >{{ link.title }}</RouterLink
        >
      </nav>
      <form class="brand-search" role="search" @submit.prevent="find">
        <UiIcon name="search" /><input
          v-model="search"
          aria-label="搜索体验商品"
          maxlength="100"
          placeholder="想体验点什么？"
        /><button type="submit" aria-label="搜索">
          <UiIcon name="arrow" />
        </button>
      </form>
      <div class="header-account">
        <RouterLink to="/orders" class="orders-link">我的订单</RouterLink
        ><RouterLink v-if="roles.length" to="/merchant" class="merchant-link"
          >商户工作台</RouterLink
        ><RouterLink
          :to="store.token ? '/InfoHtml' : '/login'"
          class="account-link"
          :aria-label="store.token ? '个人中心' : '登录'"
          ><UiIcon name="user"
        /></RouterLink>
      </div>
    </header>
    <main id="main-content" class="commerce-body" tabindex="-1"><slot /></main>
    <footer class="commerce-footer">
      <div>
        <strong>拾趣</strong>
        <p>为周末留一点新鲜感。</p>
        <p>虚构门店与演示内容，照片仅为题材配图；模拟支付不产生真实扣款。</p>
      </div>
      <div class="footer-links">
        <a :href="appUrl('content-sources.html')">图片与数据来源</a
        ><RouterLink to="/places">开放场所参考</RouterLink>
      </div>
    </footer>
    <nav class="commerce-mobile-nav" aria-label="移动商城导航">
      <RouterLink
        v-for="link in links"
        :key="link.path"
        :to="link.path"
        :class="{ current: active(link.path) }"
        :aria-current="active(link.path) ? 'page' : undefined"
        ><UiIcon :name="link.icon" /><span>{{ link.name }}</span></RouterLink
      >
    </nav>
  </div>
</template>
