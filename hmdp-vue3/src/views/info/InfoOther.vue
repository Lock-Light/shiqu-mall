<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from '@/utils/request'
import {
  me,
  image,
  fallback,
  merge,
  like,
  ensureLogin,
  notify
} from '@/utils/presentation'
import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import BlogCard from '@/components/BlogCard.vue'
const route = useRoute(),
  router = useRouter(),
  user = ref(null),
  myself = ref(null),
  rows = ref([]),
  tab = ref('notes'),
  page = ref(1),
  loading = ref(false),
  done = ref(false),
  error = ref(''),
  profileError = ref(''),
  followed = ref(false),
  following = ref(false)
let epoch = 0
async function load() {
  profileError.value = ''
  const id = String(route.params.id || '')
  if (!/^\d+$/.test(id)) {
    profileError.value = '用户不存在'
    return
  }
  try {
    user.value = (await request.get('/user/profile/' + id)).data
    myself.value = await me(true)
    if (myself.value && String(myself.value.id) === id) {
      await router.replace('/InfoHtml')
      return
    }
    if (myself.value)
      followed.value = Boolean((await request.get('/follow/or/not/' + id)).data)
    await loadMore(true)
  } catch (e) {
    profileError.value = e.message
  }
}
async function loadMore(reset = false) {
  if (!user.value || (!reset && (loading.value || done.value))) return
  const current = reset ? ++epoch : epoch
  if (reset) {
    page.value = 1
    rows.value = []
    done.value = false
  }
  loading.value = true
  error.value = ''
  try {
    let more
    if (tab.value === 'common')
      more = (await request.get('/follow/common/' + user.value.id)).data || []
    else
      more = (
        (
          await request.get('/blog/of/user', {
            params: { id: user.value.id, current: page.value }
          })
        ).data || []
      ).map((b) => ({ ...b, name: user.value.nickName, icon: user.value.icon }))
    if (current !== epoch) return
    rows.value = merge(rows.value, more)
    page.value++
    done.value = tab.value === 'common' || more.length < 10
  } catch (e) {
    if (current === epoch) error.value = e.message
  } finally {
    if (current === epoch) loading.value = false
  }
}
function setTab(value) {
  if (value === 'common' && !ensureLogin()) return
  tab.value = value
  loadMore(true)
}
async function follow() {
  if (!ensureLogin() || following.value) return
  following.value = true
  const value = !followed.value
  try {
    await request.put('/follow/' + user.value.id + '/' + value)
    followed.value = value
    user.value.fans = Math.max(
      0,
      Number(user.value.fans || 0) + (value ? 1 : -1)
    )
  } catch (e) {
    notify(e)
  } finally {
    following.value = false
  }
}
load()
</script>
<template>
  <PageHeader title="用户主页" /><StateBlock
    :error="profileError"
    @retry="load"
  /><template v-if="user && !profileError"
    ><section class="profile">
      <img :src="image(user.icon)" @error="fallback" alt="用户头像" />
      <div class="profile-main">
        <h2>{{ user.nickName }}</h2>
        <p class="muted">
          {{ user.city || '未设置城市' }} · {{ user.fans || 0 }}位粉丝
        </p>
      </div>
      <button class="secondary" :disabled="following" @click="follow">
        {{ followed ? '取消关注' : '关注作者' }}
      </button>
    </section>
    <p class="intro">{{ user.introduce || '这位用户还没有填写简介' }}</p>
    <div class="tabs">
      <button :class="{ selected: tab === 'notes' }" @click="setTab('notes')">
        探店笔记</button
      ><button
        :class="{ selected: tab === 'common' }"
        @click="setTab('common')"
      >
        共同关注
      </button>
    </div>
    <div v-if="tab === 'notes'" class="blog-grid">
      <BlogCard v-for="b in rows" :key="b.id" :blog="b" @like="like" />
    </div>
    <template v-else
      ><router-link
        class="person"
        v-for="p in rows"
        :key="p.id"
        :to="'/InfoOther/' + p.id"
        ><img :src="image(p.icon)" @error="fallback" alt="" /><span>{{
          p.nickName
        }}</span
        >›</router-link
      ></template
    ><StateBlock
      :loading="loading"
      :error="error"
      :empty="!rows.length"
      @retry="loadMore()"
    /><button
      v-if="!done && !loading && !error"
      class="load-more"
      @click="loadMore()"
    >
      加载更多
    </button></template
  >
</template>
