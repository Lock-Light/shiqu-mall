<script setup>
import { useRouter } from 'vue-router'
const props = defineProps({
    title: String,
    fallback: { type: String, default: '/index' }
  }),
  router = useRouter()
function back() {
  if (window.history.state?.back) router.back()
  else router.push(props.fallback)
}
</script>
<template>
  <header class="page-header">
    <button aria-label="返回" @click="back">‹</button>
    <h1>{{ title }}</h1>
    <slot />
  </header>
</template>
