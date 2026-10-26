<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'
import { merge } from '@/utils/presentation'
import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import ShopCard from '@/components/ShopCard.vue'
const route = useRoute(),
  router = useRouter(),
  types = ref([]),
  shops = ref([]),
  q = ref(''),
  search = ref(''),
  type = ref('1'),
  sort = ref('distance'),
  loading = ref(false),
  error = ref(''),
  done = ref(false),
  page = ref(1),
  position = ref(null),
  positionLabel = ref('演示位置'),
  locating = ref(false)
let epoch = 0
async function initialize() {
  loading.value = true
  error.value = ''
  try {
    types.value = (await request.get('/shop-type/list')).data || []
    q.value = String(route.query.q || '')
    search.value = q.value
    type.value = String(route.query.type || '1')
    sort.value = ['distance', 'score', 'comments'].includes(route.query.sort)
      ? route.query.sort
      : 'distance'
    if (!types.value.some((t) => String(t.id) === type.value))
      type.value = String(types.value[0]?.id || 1)
    if (!q.value && !position.value) {
      let saved
      try {
        saved = JSON.parse(sessionStorage.getItem('plus-position'))
      } catch {
        // Invalid browser state falls back to the default view.
      }
      if (saved && Number.isFinite(saved.x) && Number.isFinite(saved.y)) {
        position.value = saved
        positionLabel.value = '当前位置'
      } else {
        const s = (
          await request.get(
            Number(type.value) >= 21 && Number(type.value) <= 24
              ? '/shop/1001'
              : '/shop/1'
          )
        ).data
        position.value = { x: Number(s.x), y: Number(s.y) }
      }
    }
    await load(true)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
async function load(reset = false) {
  if (!reset && (loading.value || done.value)) return
  const current = reset ? ++epoch : epoch
  if (reset) {
    shops.value = []
    page.value = 1
    done.value = false
  }
  loading.value = true
  error.value = ''
  try {
    const params = { current: page.value, sortBy: sort.value }
    let url = '/shop/of/name'
    if (q.value) params.name = q.value
    else {
      url = '/shop/of/type'
      params.typeId = type.value
      if (sort.value === 'distance' && position.value)
        Object.assign(params, position.value)
    }
    const rows = (await request.get(url, { params })).data || []
    if (current !== epoch) return
    shops.value = merge(shops.value, rows)
    page.value++
    done.value = rows.length < 5
  } catch (e) {
    if (current === epoch) error.value = e.message
  } finally {
    if (current === epoch) loading.value = false
  }
}
function filters() {
  router.replace({
    path: '/shopList',
    query: q.value
      ? { q: q.value, sort: sort.value }
      : { type: type.value, sort: sort.value }
  })
}
function changeType() {
  q.value = ''
  search.value = ''
  filters()
}
function changeSort(value) {
  sort.value = value
  filters()
}
function find() {
  router.push({
    path: '/shopList',
    query: search.value.trim()
      ? { q: search.value.trim() }
      : { type: type.value }
  })
}
function locate() {
  if (locating.value) return
  if (!navigator.geolocation) {
    ElMessage.info('浏览器不支持定位')
    return
  }
  locating.value = true
  navigator.geolocation.getCurrentPosition(
    (p) => {
      position.value = { x: p.coords.longitude, y: p.coords.latitude }
      positionLabel.value = '当前位置'
      sessionStorage.setItem('plus-position', JSON.stringify(position.value))
      locating.value = false
      load(true)
    },
    () => {
      locating.value = false
      ElMessage.info('未获得定位，继续使用演示位置')
    },
    { timeout: 8000 }
  )
}
watch(() => route.fullPath, initialize, { immediate: true })
</script>
<template>
  <p class="section">
    <RouterLink to="/places">查看开放场所参考</RouterLink> ·
    OSM真实场所仅供位置参考，不代表平台入驻或在售商品。
  </p>
  <PageHeader
    :title="
      q
        ? '搜索商户'
        : types.find((t) => String(t.id) === type)?.name || '附近商户'
    "
  />
  <form class="search-form section" @submit.prevent="find">
    <input
      v-model="search"
      aria-label="搜索商户"
      placeholder="商户名称或地点"
    /><button>搜索</button>
  </form>
  <div class="sort-bar">
    <select v-model="type" aria-label="商户分类" @change="changeType">
      <option v-for="t in types" :key="t.id" :value="String(t.id)">
        {{ t.name }}
      </option></select
    ><button
      v-for="[value, label] in [
        ['distance', q ? '综合' : '距离'],
        ['comments', '人气'],
        ['score', '评分']
      ]"
      :key="value"
      :class="{ selected: sort === value }"
      @click="changeSort(value)"
    >
      {{ label }}
    </button>
  </div>
  <div v-if="!q" class="location">
    <span
      >{{ positionLabel
      }}{{ sort === 'distance' ? ' · 5公里内商户' : '' }}</span
    ><button :disabled="locating" @click="locate">
      {{ locating ? '定位中…' : '使用我的位置' }}
    </button>
  </div>
  <section class="section">
    <ShopCard v-for="s in shops" :key="s.id" :shop="s" />
  </section>
  <StateBlock
    :loading="loading"
    :error="error"
    :empty="!shops.length"
    empty-text="没有找到商户，请换个分类、关键词或位置"
    @retry="initialize"
  /><button
    v-if="!done && !loading && !error"
    class="load-more"
    @click="load()"
  >
    加载更多
  </button>
  <p v-if="done" class="end">已经到底了</p>
</template>
