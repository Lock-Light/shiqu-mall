<script setup>
import { image } from '@/utils/presentation'
defineOptions({ name: 'MallCheckout' })
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CommerceShell from '@/components/CommerceShell.vue'
import { api, requestKey, yuan } from '@/utils/commerce'
const route = useRoute(),
  router = useRouter(),
  quote = ref(null),
  loading = ref(false),
  error = ref(''),
  agreed = ref(false)
async function load() {
  error.value = ''
  try {
    quote.value = await api('/mall/skus/' + route.params.sku + '/quote')
    agreed.value = false
  } catch (e) {
    error.value = e.message
  }
}
async function submit() {
  if (loading.value || !quote.value || !agreed.value) return
  loading.value = true
  error.value = ''
  const storage =
    'mall-request:' + route.params.sku + ':' + quote.value.quoteVersion
  let key = sessionStorage.getItem(storage)
  if (!key) {
    key = requestKey()
    sessionStorage.setItem(storage, key)
  }
  try {
    const order = await api('/trade/orders', 'post', {
      skuId: String(route.params.sku),
      quoteVersion: quote.value.quoteVersion,
      requestKey: key
    })
    sessionStorage.removeItem(storage)
    await router.replace('/orders/' + order.id)
  } catch (e) {
    error.value =
      e.message + '。若请求超时，请重试同一提交或到我的订单确认结果。'
    if (e.status === 409) {
      sessionStorage.removeItem(storage)
      agreed.value = false
      try {
        quote.value = await api('/mall/skus/' + route.params.sku + '/quote')
      } catch (refreshError) {
        error.value += ' 刷新报价失败：' + refreshError.message
      }
    }
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>
<template>
  <CommerceShell
    ><div class="trade-progress" aria-label="购买进度">
      <span class="current">确认订单</span><i aria-hidden="true" /><span
        >模拟付款</span
      ><i aria-hidden="true" /><span>获取凭证</span>
    </div>
    <h1>确认体验订单</h1>
    <div v-if="error" class="mall-error" role="alert">
      {{ error }} <button @click="load">刷新报价</button>
    </div>
    <section v-if="quote" class="mall-checkout mall-panel">
      <img :src="image(quote.cover)" :alt="quote.title" />
      <div>
        <h2>{{ quote.title }}</h2>
        <p>{{ quote.name }} · 1份</p>
        <p>{{ quote.shop_name }}</p>
        <p>支付成功后 {{ quote.valid_days }} 天内使用</p>
        <p class="mall-prose">{{ quote.rules }}</p>
      </div>
      <div class="mall-checkout-summary">
        <span>应付金额</span
        ><strong class="mall-price">¥{{ yuan(quote.price) }}</strong
        ><label class="mall-agreement"
          ><input
            v-model="agreed"
            type="checkbox"
          />我已阅读使用规则，知悉当前为模拟支付</label
        ><button
          class="mall-primary"
          :disabled="loading || !agreed || Number(quote.available) <= 0"
          @click="submit"
        >
          {{ loading ? '正在创建订单…' : '提交订单，前往收银台' }}
        </button>
        <p>提交后预占库存，15分钟未付款自动关闭。</p>
        <RouterLink to="/orders">查看我的订单</RouterLink>
      </div>
    </section>
    <p v-else-if="!error">正在获取服务端报价…</p></CommerceShell
  >
</template>
