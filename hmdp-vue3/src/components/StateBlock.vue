<script setup>
defineProps({
  loading: Boolean,
  error: String,
  empty: Boolean,
  emptyText: { type: String, default: '暂无内容' }
})
defineEmits(['retry'])
</script>
<template>
  <div class="state" aria-live="polite">
    <p v-if="loading">加载中…</p>
    <div v-else-if="error" role="alert">
      <p>{{ error }}</p>
      <button class="text-button" @click="$emit('retry')">重试</button>
    </div>
    <p v-else-if="empty">{{ emptyText }}</p>
  </div>
</template>
