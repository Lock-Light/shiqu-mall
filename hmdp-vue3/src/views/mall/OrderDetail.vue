<script setup>
import { image } from '@/utils/presentation'
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import CommerceShell from '@/components/CommerceShell.vue'
import {
  api,
  labels,
  yuan,
  requestKey,
  serverMillis,
  dateLabel
} from '@/utils/commerce'
const route = useRoute(),
  order = ref(null),
  error = ref(''),
  notice = ref(''),
  busy = ref(false),
  current = ref(Date.now()),
  skew = ref(0)
const seconds = computed(() =>
  Math.max(
    0,
    Math.ceil(
      (serverMillis(order.value?.expires_at) - current.value + skew.value) /
        1000
    )
  )
)
const countdown = computed(
  () =>
    Math.floor(seconds.value / 60) +
    ':' +
    String(seconds.value % 60).padStart(2, '0')
)
async function load() {
  error.value = ''
  try {
    const result = await api('/trade/orders/' + route.params.id)
    order.value = result
    skew.value = Date.now() - serverMillis(result.serverTime)
  } catch (e) {
    error.value = e.message
  }
}
async function pay(outcome) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  const storage = 'mall-payment:' + route.params.id + ':' + outcome
  let key = sessionStorage.getItem(storage)
  if (!key) {
    key = requestKey()
    sessionStorage.setItem(storage, key)
  }
  try {
    order.value = await api(
      '/trade/orders/' + route.params.id + '/mock-pay',
      'post',
      { requestKey: key, outcome }
    )
    skew.value = Date.now() - serverMillis(order.value.serverTime)
    sessionStorage.removeItem(storage)
    notice.value =
      order.value.status === 'WAIT_PAY'
        ? '本次模拟支付失败，订单仍待付款，期限内可以重新尝试。'
        : order.value.status === 'CLOSED'
          ? '订单已关闭，没有产生付款。'
          : '支付状态已由服务端确认。'
  } catch (e) {
    error.value =
      e.message + '。结果未确认时请刷新订单状态；同一操作重试会复用请求编号。'
  } finally {
    busy.value = false
  }
}
async function cancel() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    order.value = await api(
      '/trade/orders/' + route.params.id + '/cancel',
      'post',
      {}
    )
    notice.value = '订单已关闭。'
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
watch(
  () => order.value?.status,
  (status) => {
    if (status && route.path === '/orders/' + order.value.id)
      document.title =
        (status === 'WAIT_PAY' ? '模拟收银台' : labels[status] + '订单') +
        '｜拾趣'
  }
)
const timer = setInterval(() => {
  current.value = Date.now()
}, 1000)
onMounted(load)
onUnmounted(() => clearInterval(timer))
</script>
<template>
  <CommerceShell
    ><RouterLink class="mall-back" to="/orders">返回我的订单</RouterLink>
    <div v-if="error" class="mall-error" role="alert">
      {{ error }}
      <button :disabled="busy" @click="load">重新确认订单状态</button>
    </div>
    <p v-if="notice" role="status" class="mall-notice">{{ notice }}</p>
    <template v-if="order"
      ><div class="mall-section-heading">
        <div>
          <p class="mall-kicker">订单 {{ order.id }}</p>
          <h1>{{ labels[order.status] }}</h1>
        </div>
        <button @click="load">刷新订单状态</button>
      </div>
      <div class="mall-order-layout">
        <section class="mall-panel">
          <div class="mall-order-summary">
            <img :src="image(order.cover)" :alt="order.title" />
            <div>
              <h2>{{ order.title }}</h2>
              <p>{{ order.sku_name }} · 一份</p>
              <p>{{ order.shop_name }}</p>
              <strong class="mall-price">¥{{ yuan(order.amount) }}</strong>
            </div>
          </div>
          <h3>使用规则</h3>
          <p class="mall-prose">{{ order.rules }}</p>
          <h3>订单进度</h3>
          <ol class="mall-timeline">
            <li
              v-for="event in order.events"
              :key="event.created_at + event.event_type"
            >
              <strong>{{ event.detail }}</strong
              ><small>{{ dateLabel(event.created_at) }}</small>
            </li>
          </ol>
        </section>
        <aside class="mall-panel mall-payment">
          <template v-if="order.status === 'WAIT_PAY'"
            ><h2>模拟收银台</h2>
            <p class="mall-notice">学习演示，不产生真实扣款。</p>
            <p>
              剩余付款时间 <strong>{{ countdown }}</strong>
            </p>
            <p>
              应付 <strong class="mall-price">¥{{ yuan(order.amount) }}</strong>
            </p>
            <button
              class="mall-primary"
              :disabled="busy || seconds <= 0 || !order.mockPaymentEnabled"
              @click="pay('SUCCESS')"
            >
              模拟支付成功</button
            ><button
              :disabled="busy || seconds <= 0 || !order.mockPaymentEnabled"
              @click="pay('FAILED')"
            >
              模拟支付失败</button
            ><button :disabled="busy" @click="cancel">取消待支付订单</button
            ><RouterLink to="/orders">稍后支付，返回订单</RouterLink>
            <p v-if="seconds <= 0">
              付款期限已到，请刷新查看关闭结果。
            </p></template
          ><template v-else-if="order.redemption"
            ><h2>到店电子凭证</h2>
            <p>向所属门店出示以下凭证码，整份套餐一次核销。</p>
            <code class="mall-redemption-code">{{
              order.redemption.code
            }}</code>
            <p>门店：{{ order.shop_name }}</p>
            <p>有效期至 {{ dateLabel(order.redemption.expires_at) }}</p>
            <strong>{{
              order.status === 'PAID' ? '待门店核销' : labels[order.status]
            }}</strong></template
          ><template v-else
            ><h2>订单已关闭</h2>
            <p>
              {{
                order.close_reason === 'PAYMENT_TIMEOUT'
                  ? '付款超时，预占库存已释放。'
                  : '订单已取消，未发生真实扣款。'
              }}
            </p>
            <RouterLink to="/index">重新挑选体验</RouterLink></template
          >
        </aside>
      </div></template
    >
    <p v-else-if="!error">正在确认服务端订单状态…</p></CommerceShell
  >
</template>
