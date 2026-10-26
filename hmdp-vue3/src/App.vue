<script setup>
import { RouterView } from 'vue-router'
import { useRoute } from 'vue-router'
import '@/assets/css/commerce.css'
import '@/assets/css/brand.css'
import CommerceShell from '@/components/CommerceShell.vue'
const route = useRoute()
</script>
<template>
  <div class="app-shell commerce-shell">
    <RouterView v-if="route.meta.commerce" :key="$route.path" />
    <CommerceShell v-else><RouterView :key="$route.path" /></CommerceShell>
  </div>
</template>
