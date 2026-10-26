<script setup>
import { image } from '@/utils/presentation'
import { appUrl } from '@/utils/publicPath'
import { ref, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CommerceShell from '@/components/CommerceShell.vue'
import SeckillPurchase from '@/components/SeckillPurchase.vue'
import { api, yuan } from '@/utils/commerce'
const route = useRoute(),
  router = useRouter(),
  product = ref(null),
  selected = ref(''),
  error = ref(''),
  loading = ref(false),
  selectedPhoto = ref('')
const sku = computed(() =>
  product.value?.skus.find((s) => String(s.id) === selected.value)
)
async function load() {
  loading.value = true
  error.value = ''
  const path = route.path
  try {
    product.value = await api('/mall/products/' + route.params.id)
    if (route.path === path) document.title = product.value.title + '｜拾趣'
    selectedPhoto.value =
      product.value.gallery?.[0]?.image_url || product.value.cover
    selected.value = String(
      product.value.skus.find((s) => String(s.id) === String(route.query.sku))
        ?.id ||
        product.value.skus[0]?.id ||
        ''
    )
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
function backToCatalog() {
  if (String(window.history.state?.back || '').startsWith('/index'))
    router.back()
  else router.push('/index')
}
watch(() => route.params.id, load, { immediate: true })
</script>
<template>
  <CommerceShell class="product-page"
    ><button class="mall-back" @click="backToCatalog">返回体验商城</button>
    <p v-if="loading" role="status">正在加载体验…</p>
    <div v-else-if="error" class="mall-error" role="alert">
      {{ error }} <button @click="load">重试</button>
    </div>
    <template v-else-if="product"
      ><div class="mall-detail">
        <div>
          <img
            class="mall-detail-image"
            :src="image(selectedPhoto)"
            :alt="product.title + '题材演示配图，非门店实景'"
          />
          <div
            v-if="product.gallery?.length"
            class="mall-gallery"
            aria-label="商品图集"
          >
            <button
              v-for="photo in product.gallery"
              :key="photo.asset_id"
              :aria-label="'查看' + photo.caption"
              :aria-pressed="selectedPhoto === photo.image_url"
              @click="selectedPhoto = photo.image_url"
            >
              <img :src="image(photo.thumbnail_url)" :alt="photo.caption" />
            </button>
          </div>
          <p class="mall-photo-credit">
            开放许可题材配图，非虚构门店实景。<a
              :href="appUrl('content-sources.html')"
              target="_blank"
              rel="noopener"
              >作者、原图与许可</a
            >
          </p>
          <section class="mall-panel">
            <h2>体验内容</h2>
            <p class="mall-prose">{{ product.description }}</p>
            <h2>到店信息</h2>
            <RouterLink :to="'/shopDetail/' + product.shop_id">{{
              product.shop_name
            }}</RouterLink>
            <p>{{ product.address }}</p>
            <template v-if="product.shop_profile?.introduction">
              <p class="mall-prose">{{ product.shop_profile.introduction }}</p>
              <p>营业时间：{{ product.shop_profile.hours }}</p>
              <p class="mall-prose">
                到店提示：{{ product.shop_profile.arrival_tips }}
              </p>
            </template>
            <h2>使用须知</h2>
            <p class="mall-prose">{{ product.rules }}</p>
          </section>
        </div>
        <aside class="mall-purchase">
          <span class="mall-tag">{{ product.category }}体验</span>
          <h1>{{ product.title }}</h1>
          <p>{{ product.shop_name }}</p>
          <strong class="mall-price">¥{{ yuan(sku?.price) }}</strong>
          <p>选择套餐规格</p>
          <div class="mall-sku-options">
            <button
              v-for="item in product.skus"
              :key="item.id"
              :class="{ selected: selected === String(item.id) }"
              :aria-pressed="selected === String(item.id)"
              @click="selected = String(item.id)"
            >
              <span>{{ item.name }}</span
              ><strong>¥{{ yuan(item.price) }}</strong>
            </button>
          </div>
          <p v-if="sku">
            可售 {{ sku.available }} 份 · 支付后 {{ sku.valid_days }} 天内使用
          </p>
          <SeckillPurchase
            v-if="sku?.sale_mode === 'SECKILL'"
            :key="sku.id"
            :sku="sku"
          />
          <button
            v-else
            class="mall-primary mall-buy ordinary-buy"
            :disabled="!sku || Number(sku.available) <= 0"
            @click="router.push('/checkout/' + sku.id)"
          >
            {{
              sku && Number(sku.available) > 0 ? '立即购买' : '该规格已售罄'
            }}</button
          ><small>每单一份套餐，到店一次核销。当前仅模拟支付。</small>
        </aside>
      </div></template
    >
    <div v-if="sku && sku.sale_mode !== 'SECKILL'" class="mobile-buybar">
      <div>
        <small>{{ sku.name }}</small
        ><strong>¥{{ yuan(sku.price) }}</strong>
      </div>
      <button
        class="mall-primary"
        :disabled="Number(sku.available) <= 0"
        @click="router.push('/checkout/' + sku.id)"
      >
        {{ Number(sku.available) > 0 ? '立即购买' : '该规格已售罄' }}
      </button>
    </div>
  </CommerceShell>
</template>
