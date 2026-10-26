<script setup>
import { image } from '@/utils/presentation'
import { ref, watch, onUnmounted } from 'vue'
import UiIcon from '@/components/UiIcon.vue'
import { useRoute, useRouter } from 'vue-router'
import CommerceShell from '@/components/CommerceShell.vue'
import { api, yuan } from '@/utils/commerce'
const route = useRoute(),
  router = useRouter()
const rows = ref([]),
  total = ref(0),
  loading = ref(false),
  error = ref('')
let epoch = 0
async function load() {
  if (route.path !== '/index') return
  const ticket = ++epoch
  loading.value = true
  error.value = ''
  try {
    const result = await api(
      '/mall/products?' +
        new URLSearchParams({
          q: route.query.q || '',
          category: route.query.category || '',
          page: route.query.page || 1,
          sort: route.query.sort || 'explore'
        })
    )
    if (ticket === epoch) {
      rows.value = result.list
      total.value = Number(result.total)
    }
  } catch (e) {
    if (ticket === epoch) error.value = e.message
  } finally {
    if (ticket === epoch) loading.value = false
  }
}
function filter(changes) {
  router.push({
    path: '/index',
    query: { ...route.query, page: 1, ...changes },
    hash: '#experiences'
  })
}
onUnmounted(() => {
  epoch++
})
watch(
  () => [
    route.query.q,
    route.query.category,
    route.query.page,
    route.query.sort
  ],
  load,
  { immediate: true }
)
</script>
<template>
  <CommerceShell>
    <section
      v-if="
        !route.query.q &&
        !route.query.category &&
        Number(route.query.page || 1) === 1
      "
      class="mall-hero"
    >
      <div class="mall-hero-copy">
        <span class="mall-kicker">运动 / 手作 / 文娱 / 休闲</span>
        <h1>把周末，<br />交给好奇心。</h1>
        <p>走进一项新爱好，让日常多一点意想不到。</p>
        <a
          href="#experiences"
          class="mall-primary hero-cta"
          aria-label="找到我的新体验"
          ><span>找到我的新体验</span><UiIcon name="arrow"
        /></a>
      </div>
      <div class="mall-hero-photo">
        <img
          src="/imgs/content/climb2.webp"
          alt="抱石攀岩题材照片，非门店实景"
          fetchpriority="high"
        /><a href="#experiences" class="photo-label"
          ><span
            ><strong>第一条线路，从这里开始</strong
            ><small>新手抱石体验 · 题材配图</small></span
          ><UiIcon name="arrow"
        /></a>
      </div>
    </section>
    <section id="experiences" class="mall-section" :aria-busy="loading">
      <div class="mall-section-heading">
        <div>
          <h2>有意思，值得一试。</h2>
          <p>从喜欢的事开始，发现自己的另一面。</p>
        </div>
        <span>{{ total }} 个体验商品</span>
      </div>
      <div class="mall-filter">
        <div class="mall-chips">
          <button
            v-for="category in ['', '运动', '手作', '文娱', '休闲']"
            :key="category"
            :class="{ selected: (route.query.category || '') === category }"
            :aria-pressed="(route.query.category || '') === category"
            @click="filter({ category })"
          >
            {{ category || '全部体验' }}
          </button>
        </div>
        <label
          >排序
          <select
            :value="route.query.sort || 'explore'"
            @change="filter({ sort: $event.target.value })"
          >
            <option value="explore">多样体验</option>
            <option value="newest">最新上架</option>
            <option value="price">价格从低到高</option>
            <option value="price_desc">价格从高到低</option>
          </select></label
        >
      </div>
      <p v-if="loading" role="status" class="mall-empty">正在寻找体验…</p>
      <div v-else-if="error" role="alert" class="mall-error">
        {{ error }} <button @click="load">重新加载</button>
      </div>
      <div v-else-if="!rows.length" class="mall-empty">
        没有找到符合条件的体验，试试其他分类或关键词。<button
          @click="router.push('/index#experiences')"
        >
          清除筛选
        </button>
      </div>
      <div v-else class="mall-grid">
        <RouterLink
          v-for="product in rows"
          :key="product.id"
          :to="'/products/' + product.id"
          class="mall-card"
          ><div class="mall-card-image">
            <img
              :src="image(product.cover)"
              :alt="product.title + '题材演示配图，非门店实景'"
              loading="lazy"
              decoding="async"
            /><span>{{ product.category }}</span>
          </div>
          <div class="mall-card-copy">
            <h3>{{ product.title }}</h3>
            <p>{{ product.shop_name }}</p>
            <div class="mall-card-bottom">
              <strong>¥{{ yuan(product.min_price) }}<small>起</small></strong
              ><span>{{
                Number(product.available) > 0 ? '选择体验' : '暂时售罄'
              }}</span>
            </div>
          </div></RouterLink
        >
      </div>
      <div v-if="total > 12" class="mall-pagination">
        <button
          :disabled="Number(route.query.page || 1) <= 1"
          @click="
            router.push({
              query: {
                ...route.query,
                page: Number(route.query.page || 1) - 1
              },
              hash: '#experiences'
            })
          "
        >
          上一页</button
        ><span>第 {{ route.query.page || 1 }} 页</span
        ><button
          :disabled="Number(route.query.page || 1) * 12 >= total"
          @click="
            router.push({
              query: {
                ...route.query,
                page: Number(route.query.page || 1) + 1
              },
              hash: '#experiences'
            })
          "
        >
          下一页
        </button>
      </div>
    </section>
    <section class="mall-ribbon">
      <div>
        <h2>把灵感，变成下一次出发。</h2>
        <p>从一次体验，到多一种喜欢自己的方式。</p>
      </div>
      <RouterLink to="/discover"
        >看看体验分享 <UiIcon name="arrow"
      /></RouterLink>
    </section>
  </CommerceShell>
</template>
