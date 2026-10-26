<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores'
import { api, requestKey, dateLabel } from '@/utils/commerce'
const props = defineProps({ sku: { type: Object, required: true } })
const router = useRouter(),
  route = useRoute(),
  busy = ref(false),
  message = ref(''),
  error = ref(''),
  reservation = ref('')
let alive = true
onUnmounted(() => {
  alive = false
})
const storage = () => 'mall-reservation:' + props.sku.activity_id
async function query() {
  if (!reservation.value || busy.value) return
  busy.value = true
  error.value = ''
  try {
    for (let i = 0; i < 8 && alive; i++) {
      const result = await api(
        '/trade/activities/' +
          props.sku.activity_id +
          '/result?reservationId=' +
          reservation.value
      )
      if (!alive) return
      if (result.orderId) {
        sessionStorage.removeItem(storage())
        await router.push('/orders/' + result.orderId)
        return
      }
      if (result.status === 'REJECTED') {
        message.value = result.reason || '本次资格未能落单，请重新尝试'
        sessionStorage.removeItem(storage())
        reservation.value = ''
        return
      }
      message.value = '资格已受理，正在等待数据库实际落单。'
      await new Promise((resolve) => setTimeout(resolve, 1000))
    }
    if (alive)
      message.value = '仍在排队处理中，可稍后查询本次结果，请勿反复抢购。'
  } catch (e) {
    if (alive) error.value = e.message + '，请查询已有抢购结果。'
  } finally {
    if (alive) busy.value = false
  }
}
async function reserve() {
  if (busy.value) return
  if (!useUserStore().token) {
    router.push({
      path: '/login',
      query: { redirect: route.path + '?sku=' + props.sku.id }
    })
    return
  }
  error.value = ''
  busy.value = true
  try {
    const r = await api(
      '/trade/activities/' + props.sku.activity_id + '/reserve',
      'post',
      { requestKey: requestKey() }
    )
    reservation.value = r.reservationId
    sessionStorage.setItem(storage(), reservation.value)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
  if (reservation.value && alive) await query()
}
onMounted(() => {
  reservation.value = sessionStorage.getItem(storage()) || ''
})
</script>
<template>
  <section class="mall-seckill">
    <p class="mall-tag">限量活动 · 每人一份有效订单</p>
    <p>{{ dateLabel(sku.starts_at) }} 至 {{ dateLabel(sku.ends_at) }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <p v-if="error" role="alert" class="mall-error">{{ error }}</p>
    <button
      class="mall-primary mall-buy"
      :disabled="busy || sku.activity_status !== 'ACTIVE'"
      @click="reserve"
    >
      {{ busy ? '正在查询落单结果…' : '抢购限量体验' }}</button
    ><button v-if="reservation" :disabled="busy" @click="query">
      查询上次抢购结果</button
    ><small>受理不等于购买成功，落单后仍需在期限内模拟付款。</small>
  </section>
</template>
