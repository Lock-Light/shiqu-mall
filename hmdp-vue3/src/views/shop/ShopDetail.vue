<script setup>
import { appUrl } from '@/utils/publicPath'
import { ref, reactive, computed, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'
import { useUserStore } from '@/stores'
import {
  images,
  text,
  date,
  money,
  like,
  share,
  ensureLogin,
  notify,
  merge
} from '@/utils/presentation'
import {
  issueSeckillAccessToken,
  seckillVoucher,
  getSeckillOrderId,
  getVoucherOrderIdByVoucherId,
  cancelVoucherOrder,
  subscribeVoucher,
  unsubscribeVoucher,
  getSubscribeStatusBatch
} from '@/api/voucher'
import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import BlogCard from '@/components/BlogCard.vue'
const route = useRoute(),
  store = useUserStore(),
  shop = ref(null),
  profile = ref(null),
  vouchers = ref([]),
  notes = ref([]),
  loading = ref(true),
  error = ref(''),
  voucherError = ref(''),
  notesError = ref(''),
  notesLoading = ref(false),
  notesDone = ref(false),
  notesPage = ref(1),
  now = ref(Date.now()),
  rulesOpen = ref(false),
  rulesText = ref(''),
  pending = reactive({}),
  purchased = reactive({}),
  subscriptions = reactive({}),
  messages = reactive({})
const shopImages = computed(() => images(shop.value?.images))
let alive = true
const timer = setInterval(() => {
  now.value = Date.now()
}, 1000)
onUnmounted(() => {
  alive = false
  clearInterval(timer)
})
async function load() {
  loading.value = true
  error.value = ''
  const id = String(route.params.id || '')
  if (!/^\d+$/.test(id)) {
    error.value = '商户不存在'
    loading.value = false
    return
  }
  try {
    shop.value = (await request.get('/shop/' + id)).data
    profile.value = (await request.get('/mall/shops/' + id)).data
    await Promise.all([loadVouchers(), loadNotes(true)])
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
async function loadVouchers() {
  voucherError.value = ''
  try {
    vouchers.value =
      (await request.get('/voucher/list/' + shop.value.id)).data || []
    if (store.token) {
      const ids = vouchers.value
        .filter((v) => Number(v.type) === 1)
        .map((v) => String(v.id))
      await Promise.all(
        ids.map(async (id) => {
          purchased[id] = Boolean((await getVoucherOrderIdByVoucherId(id)).data)
        })
      )
      if (ids.length) {
        const rows = (await getSubscribeStatusBatch(ids)).data || []
        rows.forEach((row) => {
          subscriptions[row.voucherId] = Number(row.subscribeStatus)
        })
      }
    }
  } catch (e) {
    voucherError.value = e.message
  }
}
async function loadNotes(reset = false) {
  if (notesLoading.value || (!reset && notesDone.value)) return
  if (reset) {
    notes.value = []
    notesPage.value = 1
    notesDone.value = false
  }
  notesLoading.value = true
  notesError.value = ''
  try {
    const rows =
      (
        await request.get('/blog/of/shop', {
          params: { id: shop.value.id, current: notesPage.value }
        })
      ).data || []
    notes.value = merge(notes.value, rows)
    notesPage.value++
    notesDone.value = rows.length < 10
  } catch (e) {
    notesError.value = e.message
  } finally {
    notesLoading.value = false
  }
}
function state(v) {
  if (pending[v.id]) return '处理中…'
  if (Number(v.type) !== 1) return '查看使用规则'
  if (purchased[v.id]) return '已领取'
  if (
    v.beginTime &&
    new Date(String(v.beginTime).replace(' ', 'T')).getTime() > now.value
  )
    return '尚未开始'
  if (
    v.endTime &&
    new Date(String(v.endTime).replace(' ', 'T')).getTime() < now.value
  )
    return '已结束'
  if (Number(v.stock) <= 0) return '已抢完'
  return '限时抢购'
}
function rules(v) {
  rulesText.value = text(v.rules || v.subTitle || '详情请咨询商户')
  rulesOpen.value = true
}
async function buy(v) {
  if (Number(v.type) !== 1) {
    rules(v)
    return
  }
  if (!ensureLogin() || state(v) !== '限时抢购') return
  pending[v.id] = true
  messages[v.id] = '正在获取抢购资格…'
  try {
    const token = (await issueSeckillAccessToken(v.id)).data
    const orderId = String((await seckillVoucher(v.id, String(token))).data)
    messages[v.id] = '请求已受理，正在确认数据库落单：' + orderId
    let committed = false
    for (let i = 0; i < 24 && alive; i++) {
      try {
        if ((await getSeckillOrderId(orderId)).data) {
          committed = true
          break
        }
      } catch (e) {
        if (e.auth) throw e
      }
      await new Promise((resolve) => setTimeout(resolve, 500))
    }
    if (!alive) return
    if (committed) {
      purchased[v.id] = true
      messages[v.id] = '数据库落单成功，订单号：' + orderId
      await loadVouchers()
    } else messages[v.id] = '订单仍在处理中，请稍后到我的订单确认：' + orderId
  } catch (e) {
    messages[v.id] = e.message
    notify(e)
  } finally {
    pending[v.id] = false
  }
}
async function cancel(v) {
  if (!ensureLogin() || pending[v.id]) return
  try {
    await ElMessageBox.confirm('确认取消领取？优惠券库存将回补。', '取消领取', {
      confirmButtonText: '确认取消',
      cancelButtonText: '保留'
    })
  } catch {
    return
  }
  pending[v.id] = true
  try {
    const { data } = await cancelVoucherOrder(String(v.id))
    if (data !== true && data !== 'true') throw new Error('取消未完成，请重试')
    purchased[v.id] = false
    messages[v.id] = '已取消领取'
    await loadVouchers()
  } catch (e) {
    messages[v.id] = e.message
    notify(e)
  } finally {
    pending[v.id] = false
  }
}
async function subscribe(v) {
  if (!ensureLogin() || pending[v.id]) return
  pending[v.id] = true
  try {
    const subscribed = subscriptions[v.id] === 1
    await (subscribed
      ? unsubscribeVoucher(String(v.id))
      : subscribeVoucher(String(v.id)))
    subscriptions[v.id] = subscribed ? 0 : 1
    ElMessage.success(subscribed ? '已取消订阅' : '已订阅到券提醒')
  } catch (e) {
    notify(e)
  } finally {
    pending[v.id] = false
  }
}
load()
</script>
<template>
  <PageHeader :title="shop?.name || '商户详情'"
    ><button class="header-action" @click="share">分享</button></PageHeader
  ><StateBlock :loading="loading" :error="error" @retry="load" /><template
    v-if="shop && !error"
    ><section class="section">
      <h2 class="detail-title">{{ shop.name }}</h2>
      <div v-if="!profile?.provenance" class="rating">
        <el-rate :model-value="Number(shop.score || 0) / 10" disabled /><span
          >{{ shop.comments || 0 }}条评价</span
        >
      </div>
      <p>{{ shop.address }}</p>
      <p class="muted">营业时间：{{ shop.openHours || '请咨询商户' }}</p>
      <template v-if="profile?.introduction">
        <p class="plain-text">{{ profile.introduction }}</p>
        <h3>适合人群</h3>
        <p>{{ profile.audience }}</p>
        <h3>到店提示</h3>
        <p>{{ profile.arrival_tips }}</p>
        <p class="muted">
          {{ profile.provenance }}
          <a :href="appUrl('content-sources.html')">图片作者与许可</a>
        </p>
        <h3>本店体验商品</h3>
        <p v-for="item in profile.products" :key="item.id">
          <RouterLink :to="'/products/' + item.id">{{ item.title }}</RouterLink>
        </p>
      </template>
      <div class="shop-images">
        <el-image
          v-for="src in shopImages"
          :key="src"
          :src="src"
          fit="cover"
          :preview-src-list="shopImages"
          ><template #error
            ><span class="image-error">图片暂不可用</span></template
          ></el-image
        >
      </div>
    </section>
    <div class="divider" />
    <section class="section">
      <h2 class="section-title">商户优惠券</h2>
      <StateBlock
        :error="voucherError"
        :empty="!vouchers.length"
        empty-text="暂无优惠券"
        @retry="loadVouchers"
      />
      <article class="voucher" v-for="v in vouchers" :key="v.id">
        <div class="voucher-main">
          <h3>{{ v.title }}</h3>
          <p>{{ v.subTitle }}</p>
          <div class="voucher-price">
            ¥{{ money(v.payValue) }}
            <small>抵¥{{ money(v.actualValue) }}</small>
          </div>
          <button class="text-button" @click="rules(v)">使用规则</button>
          <p v-if="messages[v.id]" class="coupon-message" aria-live="polite">
            {{ messages[v.id] }}
          </p>
          <router-link
            v-if="messages[v.id] || purchased[v.id]"
            class="text-button"
            to="/InfoHtml?tab=orders"
            >查看我的订单</router-link
          >
        </div>
        <div class="voucher-actions">
          <button
            class="primary"
            :disabled="Number(v.type) === 1 && state(v) !== '限时抢购'"
            @click="buy(v)"
          >
            {{ state(v) }}</button
          ><template v-if="Number(v.type) === 1"
            ><p>剩余{{ v.stock || 0 }}张</p>
            <p class="time">
              {{ date(v.beginTime) }}<br />至{{ date(v.endTime) }}
            </p>
            <button
              v-if="purchased[v.id]"
              class="text-button"
              :disabled="pending[v.id]"
              @click="cancel(v)"
            >
              取消领取</button
            ><button
              v-else
              class="text-button"
              :disabled="pending[v.id] || state(v) === '已结束'"
              @click="subscribe(v)"
            >
              {{ subscriptions[v.id] === 1 ? '取消订阅' : '订阅到券提醒' }}
            </button></template
          >
        </div>
      </article>
    </section>
    <div class="divider" />
    <section class="section">
      <h2 class="section-title">相关探店笔记</h2>
      <div class="blog-grid">
        <BlogCard v-for="b in notes" :key="b.id" :blog="b" @like="like" />
      </div>
      <StateBlock
        :loading="notesLoading"
        :error="notesError"
        :empty="!notes.length"
        @retry="loadNotes()"
      /><button
        v-if="!notesDone && !notesLoading && !notesError"
        class="load-more"
        @click="loadNotes()"
      >
        更多相关笔记</button
      ><router-link class="text-button" to="/blogEdit"
        >发布探店笔记</router-link
      >
    </section></template
  ><el-dialog v-model="rulesOpen" title="使用规则"
    ><p class="plain-text voucher-rules">{{ rulesText }}</p>
    <template #footer
      ><button class="primary" @click="rulesOpen = false">
        知道了
      </button></template
    ></el-dialog
  >
</template>
