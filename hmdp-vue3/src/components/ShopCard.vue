<script setup>
import { image, images, fallback } from '@/utils/presentation'
defineProps({ shop: Object })
</script>
<template>
  <router-link class="shop-card" :to="'/shopDetail/' + shop.id"
    ><img
      :src="images(shop.images)[0] || image('/imgs/blogs/blog1.jpg')"
      :alt="shop.name"
      @error="fallback"
    />
    <div>
      <h2>{{ shop.name }}</h2>
      <div v-if="!shop.name?.includes('虚构演示')" class="rating">
        <el-rate :model-value="Number(shop.score || 0) / 10" disabled /><span
          >{{ shop.comments || 0 }}条评价</span
        >
      </div>
      <p>
        {{ shop.area }}
        <span
          v-if="
            shop.distance !== null &&
            shop.distance !== undefined &&
            shop.distance !== ''
          "
          >·
          {{
            Number(shop.distance) < 1000
              ? Math.round(Number(shop.distance)) + 'm'
              : (Number(shop.distance) / 1000).toFixed(1) + 'km'
          }}</span
        >
      </p>
      <p v-if="!shop.name?.includes('虚构演示')">
        ¥{{ shop.avgPrice || 0 }} / 人
      </p>
      <p v-else class="muted">虚构体验门店 · 查看套餐与到店提示</p>
      <p class="muted">{{ shop.address }}</p>
    </div></router-link
  >
</template>
