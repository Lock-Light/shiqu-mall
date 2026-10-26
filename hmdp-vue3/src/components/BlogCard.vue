<script setup>
import { image, images, fallback } from '@/utils/presentation'
defineProps({ blog: Object })
defineEmits(['like'])
</script>
<template>
  <article class="blog-card">
    <router-link :to="'/blogDetail/' + blog.id"
      ><img
        class="cover"
        :src="images(blog.images)[0] || image('/imgs/blogs/blog1.jpg')"
        :alt="blog.title"
        @error="fallback"
        loading="lazy"
      />
      <h3>{{ blog.title }}</h3></router-link
    >
    <div class="blog-meta">
      <router-link class="author" :to="'/InfoOther/' + blog.userId"
        ><img :src="image(blog.icon)" alt="" @error="fallback" /><span>{{
          blog.name || '探店用户'
        }}</span></router-link
      ><button
        :aria-label="blog.isLike ? '取消点赞' : '点赞'"
        :disabled="blog.busy"
        :class="{ liked: blog.isLike }"
        @click="$emit('like', blog)"
      >
        ♡ {{ blog.liked || 0 }}
      </button>
    </div>
  </article>
</template>
