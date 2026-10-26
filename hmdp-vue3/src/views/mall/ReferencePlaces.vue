<script setup>
import { appUrl } from '@/utils/publicPath'
import { ref, onMounted } from 'vue'
import CommerceShell from '@/components/CommerceShell.vue'
import { api } from '@/utils/commerce'
const items = ref([]),
  total = ref(0),
  page = ref(1),
  q = ref(''),
  loading = ref(false),
  error = ref('')
async function load(reset = false) {
  if (loading.value) return
  if (reset) page.value = 1
  loading.value = true
  error.value = ''
  try {
    const result = await api(
      '/mall/places?' + new URLSearchParams({ q: q.value, page: page.value })
    )
    items.value = result.list
    total.value = Number(result.total)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
function turn(delta) {
  page.value += delta
  load()
}
onMounted(() => load())
</script>
<template>
  <CommerceShell>
    <RouterLink to="/shopList?type=21">返回演示门店</RouterLink>
    <h1>上海开放场所参考</h1>
    <p>
      来自OpenStreetMap的运动场所小样本，按距人民广场参考点的距离排序。地点未入驻本商城；营业状态与位置可能有变化，请核对原始记录。本页不提供套餐购买或用户评价。
    </p>
    <p>
      © OpenStreetMap contributors ·
      <a
        href="https://www.openstreetmap.org/copyright"
        target="_blank"
        rel="noopener"
        >ODbL 1.0</a
      >
      · 数据基准2026-10-24，<a :href="appUrl('content-sources.html')"
        >来源与处理说明</a
      >
    </p>
    <form class="mall-search" @submit.prevent="load(true)">
      <input
        v-model="q"
        aria-label="搜索开放场所"
        placeholder="按原始场所名称搜索"
      /><button :disabled="loading">搜索</button>
    </form>
    <p v-if="loading" role="status">正在加载场所…</p>
    <div v-if="error" class="mall-error" role="alert">
      {{ error }} <button @click="load()">重试</button>
    </div>
    <p>共 {{ total }} 个有名称的参考场所</p>
    <article v-for="place in items" :key="place.source_id" class="mall-panel">
      <h2>{{ place.name }}</h2>
      <p>
        {{ place.category === 'fitness_centre' ? '健身场所' : '运动场所' }} ·
        距参考点约 {{ (Number(place.distance_m) / 1000).toFixed(2) }} km
      </p>
      <p>{{ place.address || '原始记录未提供街道门牌' }}</p>
      <p>坐标 {{ place.longitude }}, {{ place.latitude }}</p>
      <a :href="place.source_url" target="_blank" rel="noopener"
        >查看OSM原始记录 {{ place.source_id }}</a
      >
    </article>
    <div class="mall-pagination">
      <button :disabled="loading || page <= 1" @click="turn(-1)">上一页</button
      ><span>第 {{ page }} 页</span
      ><button :disabled="loading || page * 12 >= total" @click="turn(1)">
        下一页
      </button>
    </div>
  </CommerceShell>
</template>
