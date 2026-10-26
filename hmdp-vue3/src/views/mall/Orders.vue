<script setup>
import { image } from '@/utils/presentation'
defineOptions({ name: 'MallOrders' })
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CommerceShell from '@/components/CommerceShell.vue'
import { api, labels, yuan, dateLabel } from '@/utils/commerce'
const route = useRoute(),
  router = useRouter(),
  rows = ref([]),
  total = ref(0),
  error = ref(''),
  loading = ref(false)
let epoch = 0
async function load() {
  const ticket = ++epoch
  loading.value = true
  error.value = ''
  try {
    const r = await api(
      '/trade/orders?' +
        new URLSearchParams({
          page: route.query.page || 1,
          status: route.query.status || ''
        })
    )
    if (ticket === epoch) {
      rows.value = r.list
      total.value = Number(r.total)
    }
  } catch (e) {
    if (ticket === epoch) error.value = e.message
  } finally {
    if (ticket === epoch) loading.value = false
  }
}
watch(() => route.fullPath, load, { immediate: true })
</script>
<template>
  <CommerceShell
    ><div class="mall-section-heading">
      <h1>我的体验订单</h1>
      <RouterLink to="/InfoHtml?tab=orders">历史优惠券订单</RouterLink>
    </div>
    <div class="mall-chips">
      <button
        v-for="state in ['', ...Object.keys(labels)]"
        :key="state"
        :class="{ selected: (route.query.status || '') === state }"
        @click="router.push({ query: { status: state, page: 1 } })"
      >
        {{ labels[state] || '全部订单' }}
      </button>
    </div>
    <p v-if="loading" role="status">正在加载订单…</p>
    <div v-else-if="error" role="alert" class="mall-error">
      {{ error }} <button @click="load">重试</button>
    </div>
    <div v-else-if="!rows.length" class="mall-empty">
      这里还没有订单。<RouterLink to="/index">去挑选体验</RouterLink>
    </div>
    <div v-else class="mall-orders">
      <RouterLink
        v-for="order in rows"
        :key="order.id"
        :to="'/orders/' + order.id"
        class="mall-order-card"
        ><img :src="image(order.cover)" :alt="order.title" />
        <div>
          <span class="mall-tag">{{ labels[order.status] }}</span>
          <h2>{{ order.title }}</h2>
          <p>{{ order.sku_name }} · {{ order.shop_name }}</p>
          <small>{{ dateLabel(order.created_at) }} · 订单 {{ order.id }}</small>
        </div>
        <strong>¥{{ yuan(order.amount) }}</strong></RouterLink
      >
    </div>
    <div v-if="total > 12" class="mall-pagination">
      <button
        :disabled="Number(route.query.page || 1) <= 1"
        @click="
          router.push({
            query: { ...route.query, page: Number(route.query.page || 1) - 1 }
          })
        "
      >
        上一页</button
      ><span>第 {{ route.query.page || 1 }} 页</span
      ><button
        :disabled="Number(route.query.page || 1) * 12 >= total"
        @click="
          router.push({
            query: { ...route.query, page: Number(route.query.page || 1) + 1 }
          })
        "
      >
        下一页
      </button>
    </div></CommerceShell
  >
</template>
