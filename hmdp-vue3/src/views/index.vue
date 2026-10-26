<script setup>
import { appUrl } from '@/utils/publicPath'
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import request from '@/utils/request'
import { image, fallback, merge, like } from '@/utils/presentation'
import BlogCard from '@/components/BlogCard.vue'
import StateBlock from '@/components/StateBlock.vue'
const router = useRouter(),
  source = ref(useRoute().query.source === 'legacy' ? 'legacy' : 'demo'),
  types = ref([]),
  blogs = ref([]),
  search = ref(''),
  loading = ref(false),
  error = ref(''),
  typesError = ref(''),
  page = ref(1),
  done = ref(false)
async function loadTypes() {
  typesError.value = ''
  try {
    types.value = (await request.get('/shop-type/list')).data || []
  } catch (e) {
    typesError.value = e.message
  }
}
async function loadMore() {
  if (loading.value || done.value) return
  loading.value = true
  error.value = ''
  try {
    const rows =
      (
        await request.get(
          source.value === 'demo' ? '/mall/stories' : '/blog/hot',
          {
            params:
              source.value === 'demo'
                ? { page: page.value }
                : { current: page.value }
          }
        )
      ).data || []
    blogs.value = merge(blogs.value, rows)
    page.value++
    done.value = rows.length < 10
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
function find() {
  if (search.value.trim())
    router.push({ path: '/shopList', query: { q: search.value.trim() } })
}
function changeSource(value) {
  if (loading.value || source.value === value) return
  source.value = value
  blogs.value = []
  page.value = 1
  done.value = false
  loadMore()
}
loadTypes()
loadMore()
</script>
<template>
  <header class="search-header">
    <router-link to="/index" class="brand">拾趣分享</router-link>
    <form class="search-form" @submit.prevent="find">
      <input
        v-model="search"
        aria-label="搜索商户"
        placeholder="商户名称或地点"
      /><button>搜索</button>
    </form>
    <router-link to="/blogEdit" class="text-button">发布分享</router-link>
  </header>
  <div class="types">
    <button
      v-for="t in types"
      :key="t.id"
      @click="router.push({ path: '/shopList', query: { type: t.id } })"
    >
      <img :src="image(t.icon)" @error="fallback" alt="" /><span>{{
        t.name
      }}</span>
    </button>
  </div>
  <StateBlock :error="typesError" @retry="loadTypes" />
  <h2 class="section-title section">体验分享</h2>
  <div class="section">
    <button
      :disabled="loading || source === 'demo'"
      @click="changeSource('demo')"
    >
      演示体验分享
    </button>
    <button
      :disabled="loading || source === 'legacy'"
      @click="changeSource('legacy')"
    >
      上游历史示例
    </button>
    <p class="muted">
      演示分享为原创虚构记录，配图非门店实景，不作为真实用户评价。<a
        :href="appUrl('content-sources.html')"
        >照片作者与许可</a
      >
    </p>
  </div>
  <div class="blog-grid">
    <BlogCard v-for="b in blogs" :key="b.id" :blog="b" @like="like" />
  </div>
  <StateBlock
    :loading="loading"
    :error="error"
    :empty="!blogs.length"
    @retry="loadMore"
  /><button
    v-if="!done && !loading && !error"
    class="load-more"
    @click="loadMore"
  >
    加载更多
  </button>
  <p v-if="done" class="end">已经到底了</p>
</template>
