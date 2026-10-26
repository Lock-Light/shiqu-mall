<script setup>
defineOptions({ name: 'MerchantWorkspace' })
import { ref, onMounted, watch } from 'vue'
import CommerceShell from '@/components/CommerceShell.vue'
import { api, labels, yuan } from '@/utils/commerce'
const roles = ref([]),
  shops = ref([]),
  members = ref([]),
  memberUser = ref(''),
  activityForm = ref(null),
  isAdmin = ref(false),
  shop = ref(''),
  products = ref([]),
  orders = ref([]),
  error = ref(''),
  notice = ref(''),
  busy = ref(false),
  form = ref(null),
  code = ref(''),
  preview = ref(null),
  delta = ref({}),
  orderPage = ref(1)
let loadEpoch = 0
async function load() {
  if (!shop.value) return
  const epoch = ++loadEpoch,
    currentShop = shop.value,
    currentPage = orderPage.value
  error.value = ''
  try {
    const nextProducts = await api('/merchant/products?shopId=' + currentShop)
    const nextOrders = await api(
      '/merchant/orders?shopId=' + currentShop + '&page=' + currentPage
    )
    if (epoch === loadEpoch) {
      products.value = nextProducts
      orders.value = nextOrders
    }
  } catch (e) {
    if (epoch === loadEpoch) error.value = e.message
  }
}
async function init() {
  try {
    const me = await api('/mall/me')
    isAdmin.value = me.admin
    roles.value = me.memberships.filter((r) => r.role === 'MERCHANT')
    if (isAdmin.value) {
      shops.value = await api('/platform/shops')
      members.value = await api('/platform/members')
    }
    shop.value = isAdmin.value ? '1001' : String(roles.value[0]?.shop_id || '')
    if (!shop.value) error.value = '当前账号未绑定门店，请联系平台管理员。'
  } catch (e) {
    error.value = e.message
  }
}
function edit(product = null, sku = null) {
  form.value = product
    ? {
        id: product.id,
        version: product.version,
        skuId: sku.id,
        shopId: shop.value,
        title: product.title,
        category: product.category,
        cover: product.cover,
        description: product.description,
        rules: product.rules,
        status: product.status,
        skuName: sku.name,
        price: sku.price,
        validDays: sku.valid_days
      }
    : {
        shopId: shop.value,
        title: '',
        category: '运动',
        cover: '/imgs/commerce/sport.svg',
        description: '',
        rules: '支付后有效期内到店一次使用，当前仅模拟支付。',
        status: 'DRAFT',
        skuName: '单人基础套餐',
        price: '39.90',
        validDays: 30,
        stock: 10
      }
}
async function action(fn, message) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await fn()
    notice.value = message
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
async function save() {
  await action(async () => {
    await api('/merchant/products', 'post', form.value)
    form.value = null
  }, '商品已保存')
}
async function stock(sku) {
  await action(async () => {
    await api('/merchant/skus/' + sku.id + '/stock', 'post', {
      delta: Number(delta.value[sku.id]),
      version: sku.version
    })
    delta.value[sku.id] = ''
  }, '库存已调整')
}
async function inspect() {
  preview.value = null
  await action(async () => {
    preview.value = await api('/merchant/redemptions/preview', 'post', {
      code: code.value.trim()
    })
  }, '已查询凭证，请确认套餐和门店')
}
async function confirm() {
  await action(async () => {
    preview.value = await api('/merchant/redemptions/confirm', 'post', {
      code: code.value.trim()
    })
  }, '核销结果已确认')
}
async function grant() {
  await action(async () => {
    await api('/platform/members', 'post', {
      userId: memberUser.value,
      shopId: shop.value
    })
    members.value = await api('/platform/members')
    memberUser.value = ''
  }, '门店授权已保存')
}
async function revoke(member) {
  await action(async () => {
    await api(
      '/platform/members/' + member.user_id + '/' + member.shop_id,
      'delete'
    )
    members.value = await api('/platform/members')
  }, '门店授权已撤销')
}
function prepareActivity(sku) {
  const local = (offset) => {
    const d = new Date(Date.now() + offset)
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16)
  }
  activityForm.value = {
    skuId: sku.id,
    startsAt: local(-60000),
    endsAt: local(7 * 86400000)
  }
}
async function publishActivity() {
  await action(async () => {
    await api('/merchant/activities', 'post', activityForm.value)
    activityForm.value = null
  }, '限量活动已建立，该规格独占库存并冻结活动配置')
}
async function stopActivity(sku) {
  await action(async () => {
    await api('/merchant/activities/' + sku.activity_id + '/stop', 'post', {})
  }, '已停止新增资格；已有订单仍可支付、核销或到期关闭')
}
watch(shop, () => {
  form.value = null
  preview.value = null
  orderPage.value = 1
  load()
})
watch(orderPage, load)
onMounted(init)
</script>
<template>
  <CommerceShell
    ><h1>商户工作台</h1>
    <p>只可管理已授权门店；凭证由所属门店核销。</p>
    <div v-if="error" class="mall-error" role="alert">
      {{ error }} <button @click="load">重试</button>
    </div>
    <p v-if="notice" class="mall-notice" role="status">{{ notice }}</p>
    <label v-if="roles.length || isAdmin"
      >当前门店
      <select v-if="isAdmin" v-model="shop" aria-label="管理门店">
        <option v-for="item in shops" :key="item.id" :value="String(item.id)">
          {{ item.name }}
        </option></select
      ><select v-else v-model="shop" aria-label="当前门店">
        <option
          v-for="role in roles"
          :key="role.shop_id"
          :value="String(role.shop_id)"
        >
          {{ role.shop_name }}
        </option>
      </select></label
    ><template v-if="shop">
      <section v-if="isAdmin" class="mall-panel">
        <h2>平台门店授权</h2>
        <form class="mall-search" @submit.prevent="grant">
          <input
            v-model="memberUser"
            required
            inputmode="numeric"
            aria-label="授权用户编号"
            placeholder="输入已登录用户编号"
          /><button :disabled="busy">授权当前门店</button>
        </form>
        <div
          v-for="member in members.filter((m) => m.role === 'MERCHANT')"
          :key="member.user_id + '-' + member.shop_id"
          class="mall-merchant-order"
        >
          <span>用户 {{ member.user_id }} · {{ member.shop_name }}</span
          ><button :disabled="busy" @click="revoke(member)">
            撤销门店授权
          </button>
        </div>
      </section>
      <section class="mall-panel">
        <h2>凭证核销</h2>
        <form class="mall-search" @submit.prevent="inspect">
          <input
            v-model="code"
            aria-label="凭证码"
            maxlength="32"
            placeholder="输入顾客出示的32位凭证码"
          /><button :disabled="busy">查询凭证</button>
        </form>
        <div v-if="preview">
          <h3>{{ preview.title }}</h3>
          <p>
            {{ preview.sku_name }} · {{ preview.shop_name }} ·
            {{ labels[preview.status] }}
          </p>
          <button
            class="mall-primary"
            :disabled="busy || !['PAID', 'USED'].includes(preview.status)"
            @click="confirm"
          >
            {{
              preview.status === 'USED'
                ? '已核销，重新确认状态'
                : '确认核销整份套餐'
            }}
          </button>
        </div>
      </section>
      <section class="mall-panel">
        <div class="mall-section-heading">
          <h2>商品与库存</h2>
          <button @click="edit()">新建体验商品</button>
        </div>
        <form
          v-if="activityForm"
          class="mall-editor"
          @submit.prevent="publishActivity"
        >
          <h3 class="wide">建立专属限量活动</h3>
          <p class="wide">
            使用该规格全部可售库存，活动建立后不与普通购买共享库存。只允许未发生交易的规格。
          </p>
          <label
            >开始时间<input
              v-model="activityForm.startsAt"
              type="datetime-local"
              required /></label
          ><label
            >结束时间<input
              v-model="activityForm.endsAt"
              type="datetime-local"
              required
          /></label>
          <div>
            <button class="mall-primary" :disabled="busy">
              确认建立限量活动</button
            ><button type="button" @click="activityForm = null">
              放弃建立
            </button>
          </div>
        </form>
        <form v-if="form" class="mall-editor" @submit.prevent="save">
          <label
            >商品名称<input
              v-model="form.title"
              required
              maxlength="100" /></label
          ><label
            >分类<select v-model="form.category">
              <option
                v-for="category in ['运动', '手作', '文娱', '休闲']"
                :key="category"
              >
                {{ category }}
              </option>
            </select></label
          ><label
            >封面<select v-model="form.cover">
              <option value="/imgs/commerce/sport.svg">运动场景插画</option>
              <option value="/imgs/commerce/craft.svg">手作场景插画</option>
              <option value="/imgs/commerce/play.svg">文娱场景插画</option>
              <option value="/imgs/commerce/rest.svg">休闲场景插画</option>
            </select></label
          ><label
            >状态<select v-model="form.status">
              <option value="DRAFT">草稿</option>
              <option value="ACTIVE">在售</option>
              <option value="OFFLINE">下架</option>
            </select></label
          ><label
            >规格名称<input
              v-model="form.skuName"
              required
              maxlength="60" /></label
          ><label
            >价格（元）<input
              v-model="form.price"
              type="number"
              min="0.01"
              max="99999999.99"
              step="0.01"
              required /></label
          ><label
            >有效天数<input
              v-model="form.validDays"
              type="number"
              min="1"
              max="365"
              required /></label
          ><label v-if="!form.id"
            >初始库存<input
              v-model="form.stock"
              type="number"
              min="0"
              max="100000"
              required /></label
          ><label class="wide"
            >体验内容<textarea
              v-model="form.description"
              required
              maxlength="4000"
            /></label
          ><label class="wide"
            >使用规则<textarea v-model="form.rules" required maxlength="2000" />
          </label>
          <div>
            <button class="mall-primary" :disabled="busy">保存商品</button
            ><button type="button" @click="form = null">取消编辑</button>
          </div>
        </form>
        <article
          v-for="product in products"
          :key="product.id"
          class="mall-merchant-product"
        >
          <h3>
            {{ product.title }}
            <small>{{
              { ACTIVE: '在售', DRAFT: '草稿', OFFLINE: '已下架' }[
                product.status
              ]
            }}</small>
          </h3>
          <div v-for="sku in product.skus" :key="sku.id" class="mall-stock-row">
            <span
              >{{ sku.name }} ¥{{ yuan(sku.price) }}<br />可售
              {{ sku.available }} / 预占 {{ sku.reserved }} / 已售
              {{ sku.sold }}</span
            ><button
              :disabled="sku.sale_mode === 'SECKILL'"
              @click="edit(product, sku)"
            >
              编辑商品/规格</button
            ><label
              >调整量<input
                v-model="delta[sku.id]"
                type="number"
                :aria-label="sku.name + '库存调整量'"
                placeholder="如10或-2" /></label
            ><button
              :disabled="
                busy || sku.sale_mode === 'SECKILL' || !Number(delta[sku.id])
              "
              @click="stock(sku)"
            >
              调整库存
            </button>
            <button
              v-if="sku.sale_mode === 'NORMAL'"
              :disabled="
                busy ||
                Number(sku.available) <= 0 ||
                Number(sku.reserved) > 0 ||
                Number(sku.sold) > 0 ||
                product.status !== 'ACTIVE'
              "
              @click="prepareActivity(sku)"
            >
              建立限量活动</button
            ><template v-else
              ><span class="mall-tag"
                >限量活动专属规格 · {{ sku.activity_status }}</span
              ><button
                :disabled="busy || sku.activity_status === 'CLOSED'"
                @click="stopActivity(sku)"
              >
                停止新增抢购
              </button></template
            >
          </div>
        </article>
      </section>
      <section class="mall-panel">
        <h2>本店订单</h2>
        <p v-if="!orders.length">暂无订单</p>
        <div
          v-for="order in orders"
          :key="order.id"
          class="mall-merchant-order"
        >
          <span>{{ order.id }}</span
          ><strong>{{ order.title }}</strong
          ><span>{{ labels[order.status] }} · ¥{{ yuan(order.amount) }}</span>
        </div>
        <div class="mall-pagination">
          <button :disabled="orderPage <= 1" @click="orderPage--">上一页</button
          ><span>第 {{ orderPage }} 页</span
          ><button :disabled="orders.length < 12" @click="orderPage++">
            下一页
          </button>
        </div>
      </section></template
    ></CommerceShell
  >
</template>
