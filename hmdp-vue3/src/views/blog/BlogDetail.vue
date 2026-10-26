<script setup>
import { appUrl } from '@/utils/publicPath'
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import request from '@/utils/request'
import {
  me,
  text,
  date,
  image,
  images,
  fallback,
  like as toggleLike,
  share,
  ensureLogin,
  notify
} from '@/utils/presentation'
import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import ShopCard from '@/components/ShopCard.vue'
const route = useRoute(),
  blog = ref(null),
  shop = ref(null),
  user = ref(null),
  likes = ref([]),
  loading = ref(true),
  error = ref(''),
  shopError = ref(''),
  followed = ref(false),
  following = ref(false)
async function load() {
  loading.value = true
  error.value = ''
  const id = String(route.params.id || '')
  if (!/^\d+$/.test(id)) {
    error.value = '笔记不存在'
    loading.value = false
    return
  }
  try {
    blog.value = (await request.get('/blog/' + id)).data
    user.value = await me(true)
    await Promise.all([loadShop(), loadLikes()])
    if (user.value && String(user.value.id) !== String(blog.value.userId))
      followed.value = Boolean(
        (await request.get('/follow/or/not/' + blog.value.userId)).data
      )
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
async function loadShop() {
  shopError.value = ''
  try {
    shop.value = (await request.get('/shop/' + blog.value.shopId)).data
  } catch {
    shopError.value = '关联商户暂不可用'
  }
}
async function loadLikes() {
  try {
    likes.value = (await request.get('/blog/likes/' + blog.value.id)).data || []
  } catch (e) {
    notify(e)
  }
}
async function like() {
  if (!ensureLogin()) return
  await toggleLike(blog.value)
  await loadLikes()
}
async function follow() {
  if (!ensureLogin() || following.value) return
  following.value = true
  try {
    await request.put('/follow/' + blog.value.userId + '/' + !followed.value)
    followed.value = !followed.value
  } catch (e) {
    notify(e)
  } finally {
    following.value = false
  }
}
load()
</script>
<template>
  <PageHeader title="探店笔记"
    ><button class="header-action" @click="share">分享</button></PageHeader
  ><StateBlock :loading="loading" :error="error" @retry="load" /><template
    v-if="blog && !error"
    ><div class="blog-gallery">
      <el-carousel
        :autoplay="false"
        height="380px"
        :arrow="images(blog.images).length > 1 ? 'hover' : 'never'"
        ><el-carousel-item v-for="src in images(blog.images)" :key="src"
          ><el-image
            :src="src"
            fit="contain"
            :preview-src-list="images(blog.images)"
            ><template #error
              ><span class="image-error">图片暂不可用</span></template
            ></el-image
          ></el-carousel-item
        ></el-carousel
      >
    </div>
    <section class="section">
      <div class="author-row">
        <router-link class="author" :to="'/InfoOther/' + blog.userId"
          ><img :src="image(blog.icon)" @error="fallback" alt="" /><span>{{
            blog.name
          }}</span></router-link
        ><button
          v-if="!user || String(user.id) !== String(blog.userId)"
          class="secondary"
          :disabled="following"
          @click="follow"
        >
          {{ followed ? '取消关注' : '关注作者' }}
        </button>
      </div>
      <p class="muted">{{ date(blog.createTime) }}</p>
      <h2 class="detail-title">{{ blog.title }}</h2>
      <p class="plain-text blog-content">{{ text(blog.content) }}</p>
      <p v-if="blog.title?.includes('｜演示')" class="muted">
        原创虚构体验记录；照片为题材配图，非门店实景。<a
          :href="appUrl('content-sources.html')"
          >查看图片作者、原始文件和许可</a
        >
      </p>
      <button
        class="text-button"
        :class="{ liked: blog.isLike }"
        :aria-label="blog.isLike ? '取消点赞' : '点赞'"
        :disabled="blog.busy"
        @click="like"
      >
        ♡ {{ blog.isLike ? '已赞' : '点赞' }} {{ blog.liked || 0 }}
      </button>
      <div class="likers">
        <span class="muted">最近点赞</span
        ><router-link v-for="p in likes" :key="p.id" :to="'/InfoOther/' + p.id"
          ><img
            :src="image(p.icon)"
            :alt="p.nickName"
            @error="fallback" /></router-link
        ><span v-if="!likes.length" class="muted">还没有人点赞</span>
      </div>
    </section>
    <div class="divider" />
    <section class="section">
      <h2 class="section-title">关联商户</h2>
      <ShopCard v-if="shop" :shop="shop" />
      <p v-else class="muted">{{ shopError }}</p>
    </section></template
  >
</template>
