<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'
import {
  me,
  image,
  fallback,
  merge,
  like,
  money,
  date
} from '@/utils/presentation'
import { useUserStore } from '@/stores'
import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
import BlogCard from '@/components/BlogCard.vue'
const route = useRoute(),
  router = useRouter(),
  store = useUserStore(),
  user = ref(null),
  profile = ref({}),
  rows = ref([]),
  tab = ref('notes'),
  page = ref(1),
  cursor = ref({ lastId: Date.now() + 1, offset: 0 }),
  loading = ref(false),
  done = ref(false),
  error = ref(''),
  profileError = ref(''),
  signCount = ref(0),
  signed = ref(false),
  signBusy = ref(false),
  logoutBusy = ref(false)
let epoch = 0
function selected() {
  return ['notes', 'feed', 'fans', 'following', 'orders'].includes(
    route.query.tab
  )
    ? route.query.tab
    : 'notes'
}
async function load() {
  profileError.value = ''
  try {
    user.value = await me()
    profile.value = (await request.get('/user/profile/' + user.value.id)).data
    signCount.value = Number((await request.get('/user/sign/count')).data || 0)
    signed.value = signCount.value > 0
    tab.value = selected()
    await loadMore(true)
  } catch (e) {
    profileError.value = e.message
  }
}
async function loadMore(reset = false) {
  if (!user.value || (!reset && (loading.value || done.value))) return
  const current = reset ? ++epoch : epoch,
    kind = tab.value
  if (reset) {
    rows.value = []
    page.value = 1
    done.value = false
    cursor.value = { lastId: Date.now() + 1, offset: 0 }
  }
  loading.value = true
  error.value = ''
  try {
    let more = [],
      nextCursor = null
    if (kind === 'notes') {
      more = (
        (await request.get('/blog/of/me', { params: { current: page.value } }))
          .data || []
      ).map((b) => ({ ...b, name: user.value.nickName, icon: user.value.icon }))
    } else if (kind === 'feed') {
      const data =
        (await request.get('/blog/of/follow', { params: cursor.value })).data ||
        {}
      more = data.list || []
      if (data.minTime !== undefined)
        nextCursor = { lastId: data.minTime, offset: Number(data.offset || 0) }
    } else if (kind === 'orders') {
      more =
        (
          await request.get('/voucher-order/mine', {
            params: { current: page.value }
          })
        ).data || []
    } else
      more =
        (
          await request.get('/user/connections/' + user.value.id, {
            params: { kind, current: page.value }
          })
        ).data || []
    if (current !== epoch) return
    if (nextCursor) cursor.value = nextCursor
    rows.value = merge(rows.value, more)
    page.value++
    done.value = more.length < (kind === 'feed' ? 2 : 10)
  } catch (e) {
    if (current === epoch) error.value = e.message
  } finally {
    if (current === epoch) loading.value = false
  }
}
function setTab(value) {
  router.replace({ path: '/InfoHtml', query: { tab: value } })
}
watch(
  () => route.query.tab,
  () => {
    const value = selected()
    if (value !== tab.value) {
      tab.value = value
      loadMore(true)
    }
  }
)
async function sign() {
  if (signBusy.value || signed.value) return
  signBusy.value = true
  try {
    await request.post('/user/sign')
    signCount.value = Number((await request.get('/user/sign/count')).data || 0)
    signed.value = true
    ElMessage.success('签到成功')
  } catch (e) {
    error.value = e.message
  } finally {
    signBusy.value = false
  }
}
async function logout() {
  if (logoutBusy.value) return
  logoutBusy.value = true
  try {
    await request.post('/user/logout')
    store.clear()
    await router.replace('/index')
  } catch (e) {
    error.value = e.message
  } finally {
    logoutBusy.value = false
  }
}
load()
</script>
<template>
  <PageHeader title="个人主页"
    ><button class="header-action" :disabled="logoutBusy" @click="logout">
      退出登录
    </button></PageHeader
  ><StateBlock :error="profileError" @retry="load" /><template
    v-if="user && !profileError"
    ><section class="profile">
      <img :src="image(profile.icon)" @error="fallback" alt="我的头像" />
      <div class="profile-main">
        <h2>{{ profile.nickName }}</h2>
        <p class="muted">{{ profile.city || '未设置城市' }}</p>
        <div class="profile-actions">
          <RouterLink class="secondary" to="/blogEdit">发布分享</RouterLink>
          <router-link class="secondary" to="/InfoEdit">编辑资料</router-link
          ><button
            class="secondary"
            :disabled="signBusy || signed"
            @click="sign"
          >
            {{ signBusy ? '签到中…' : signed ? '今日已签到' : '每日签到' }}
          </button>
        </div>
      </div>
    </section>
    <p class="intro">
      {{ profile.introduce || '添加个人简介，让大家认识你'
      }}<span v-if="signed" class="muted"> · 连续签到{{ signCount }}天</span>
    </p>
    <div class="stats">
      <button @click="setTab('fans')">
        <strong>{{ profile.fans || 0 }}</strong
        >粉丝</button
      ><button @click="setTab('following')">
        <strong>{{ profile.followee || 0 }}</strong
        >关注</button
      ><button @click="router.push('/orders')">体验订单</button>
    </div>
    <div class="tabs" role="tablist" aria-label="个人主页内容">
      <button
        v-for="[key, label] in [
          ['notes', '我的笔记'],
          ['feed', '关注动态'],
          ['fans', '粉丝'],
          ['following', '关注的人'],
          ['orders', '历史券订单']
        ]"
        :key="key"
        role="tab"
        :aria-selected="tab === key"
        :class="{ selected: tab === key }"
        @click="setTab(key)"
      >
        {{ label }}
      </button>
    </div>
    <div v-if="tab === 'notes' || tab === 'feed'" class="blog-grid">
      <BlogCard v-for="b in rows" :key="b.id" :blog="b" @like="like" />
    </div>
    <template v-else-if="tab === 'fans' || tab === 'following'"
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
    ><template v-else
      ><article class="order" v-for="o in rows" :key="o.id">
        <h3>{{ o.title || '商户优惠券' }}</h3>
        <strong class="liked">{{
          Number(o.status) === 1
            ? '已落单 · 待支付'
            : Number(o.status) === 2
              ? '已取消'
              : '订单状态：' + o.status
        }}</strong>
        <p>订单号：{{ o.id }}</p>
        <p>金额：¥{{ money(o.payValue) }}</p>
        <p>{{ date(o.createTime) }}</p>
        <p class="muted">支付服务暂未开放</p>
        <router-link class="text-button" :to="'/shopDetail/' + (o.shopId || 1)"
          >查看商户</router-link
        >
      </article></template
    ><StateBlock
      :loading="loading"
      :error="error"
      :empty="!rows.length"
      :empty-text="
        tab === 'feed' ? '暂无关注动态，先关注感兴趣的作者吧' : '暂无内容'
      "
      @retry="loadMore()"
    /><button
      v-if="!done && !loading && !error"
      class="load-more"
      @click="loadMore()"
    >
      加载更多
    </button>
    <p v-if="done" class="end">已经到底了</p></template
  >
</template>
