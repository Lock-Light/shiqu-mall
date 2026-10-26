<script setup>
import { useRoute, useRouter } from 'vue-router'
const route = useRoute(),
  router = useRouter()
const links = [
  ['商城', '/index', '⌂'],
  ['附近', '/shopList?type=21', '⌖'],
  ['发布', '/blogEdit', '＋'],
  ['关注', '/InfoHtml?tab=feed', '♡'],
  ['我的', '/InfoHtml', '♙']
]
function active(path) {
  return path.includes('?') ? route.fullPath === path : route.path === path
}
</script>
<template>
  <nav class="foot" aria-label="底部导航">
    <button
      v-for="[name, path, icon] in links"
      :key="name"
      :aria-label="name"
      :class="{ active: active(path) }"
      @click="router.push(path)"
    >
      <span class="nav-icon">{{ icon }}</span
      >{{ name }}
    </button>
  </nav>
</template>
