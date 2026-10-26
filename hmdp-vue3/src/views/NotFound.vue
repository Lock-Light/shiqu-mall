<script setup>
import PageHeader from '@/components/PageHeader.vue'
</script>
<template>
  <PageHeader title="页面不存在" />
  <section class="section not-found">
    <strong aria-hidden="true">404</strong>
    <h2>这次探索暂时迷路了</h2>
    <p>这个页面不存在，请返回首页。</p>
    <router-link class="mall-primary" to="/index">返回首页</router-link>
  </section>
</template>
