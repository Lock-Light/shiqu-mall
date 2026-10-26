<script setup>
import { ref, reactive, watch } from 'vue'
import { useRouter, onBeforeRouteLeave } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import request from '@/utils/request'
import { me, upload, image, imagePath } from '@/utils/presentation'
import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
const router = useRouter(),
  params = reactive({ title: '', content: '' }),
  files = ref([]),
  input = ref(),
  selectedShop = ref({}),
  shops = ref([]),
  shopName = ref(''),
  showDialog = ref(false),
  shopLoading = ref(false),
  shopError = ref(''),
  uploading = ref(false),
  deleting = ref([]),
  publishing = ref(false),
  error = ref(''),
  ready = ref(false)
let draftKey = '',
  published = false,
  shopEpoch = 0
function persist() {
  if (ready.value && draftKey)
    sessionStorage.setItem(
      draftKey,
      JSON.stringify({
        params,
        files: files.value,
        selectedShop: selectedShop.value
      })
    )
}
async function load() {
  try {
    const user = await me()
    draftKey = 'plus-blog-draft:' + user.id
    try {
      const draft = JSON.parse(sessionStorage.getItem(draftKey))
      if (draft) {
        Object.assign(params, draft.params)
        files.value = (draft.files || []).map(imagePath)
        selectedShop.value = draft.selectedShop || {}
      }
    } catch {
      // Invalid browser state falls back to the default view.
    }
    ready.value = true
    queryShops()
  } catch (e) {
    error.value = e.message
  }
}
watch([params, files, selectedShop], persist, { deep: true })
async function queryShops() {
  const current = ++shopEpoch
  shopLoading.value = true
  shopError.value = ''
  try {
    const rows =
      (
        await request.get('/shop/of/name', {
          params: { name: shopName.value.trim(), current: 1 }
        })
      ).data || []
    if (current === shopEpoch) shops.value = rows
  } catch (e) {
    if (current === shopEpoch) shopError.value = e.message
  } finally {
    if (current === shopEpoch) shopLoading.value = false
  }
}
function choose(shop) {
  selectedShop.value = shop
  persist()
  showDialog.value = false
}
async function selectFiles(event) {
  const items = Array.from(event.target.files || [])
  event.target.value = ''
  if (!items.length || uploading.value || publishing.value) return
  error.value = ''
  if (files.value.length + items.length > 9) {
    error.value = '最多上传9张图片'
    return
  }
  uploading.value = true
  try {
    for (const file of items) files.value.push(await upload(file))
    persist()
  } catch (e) {
    error.value = e.message
  } finally {
    uploading.value = false
  }
}
async function remove(src) {
  if (deleting.value.includes(src) || uploading.value || publishing.value)
    return
  deleting.value.push(src)
  try {
    await request.get('/upload/blog/delete', {
      params: { name: imagePath(src) }
    })
    files.value = files.value.filter((f) => f !== src)
    persist()
  } catch (e) {
    error.value = e.message
  } finally {
    deleting.value = deleting.value.filter((f) => f !== src)
  }
}
async function publish() {
  if (
    !ready.value ||
    publishing.value ||
    uploading.value ||
    deleting.value.length
  )
    return
  error.value = ''
  if (!params.title.trim()) {
    error.value = '请填写笔记标题'
    return
  }
  if (!params.content.trim()) {
    error.value = '请填写笔记内容'
    return
  }
  if (!files.value.length) {
    error.value = '请至少上传一张图片'
    return
  }
  if (!selectedShop.value.id) {
    error.value = '请选择关联商户'
    return
  }
  publishing.value = true
  try {
    const { data } = await request.post('/blog', {
      title: params.title.trim(),
      content: params.content.trim(),
      images: files.value.join(','),
      shopId: selectedShop.value.id
    })
    published = true
    sessionStorage.removeItem(draftKey)
    await router.replace('/blogDetail/' + data)
  } catch (e) {
    error.value = e.message
  } finally {
    publishing.value = false
  }
}
onBeforeRouteLeave(async () => {
  if (published) return true
  if (publishing.value) return false
  persist()
  if (!params.title && !params.content && !files.value.length) return true
  try {
    await ElMessageBox.confirm(
      '未发布内容已作为草稿保存在当前浏览器，确认离开？',
      '保留草稿',
      { confirmButtonText: '保留并离开', cancelButtonText: '继续编辑' }
    )
    return true
  } catch {
    return false
  }
})
load()
</script>
<template>
  <PageHeader title="发布探店笔记" fallback="/InfoHtml" />
  <section class="editor">
    <p class="muted">草稿自动保存，最多9张图片，每张不超过5MB。</p>
    <input
      ref="input"
      class="file-input"
      aria-label="上传笔记图片"
      type="file"
      accept="image/png,image/jpeg,image/webp"
      multiple
      @change="selectFiles"
    />
    <div class="upload-list">
      <button
        class="upload-add"
        :disabled="uploading || publishing || files.length >= 9"
        @click="input.click()"
      >
        {{ uploading ? '上传中…' : '＋ 上传照片' }}
      </button>
      <div v-for="src in files" :key="src" class="upload-item">
        <img :src="image(src)" alt="已上传图片" /><button
          aria-label="删除图片"
          :disabled="uploading || publishing || deleting.includes(src)"
          @click="remove(src)"
        >
          ×
        </button>
      </div>
    </div>
    <label class="field"
      ><span>笔记标题</span
      ><input
        v-model="params.title"
        placeholder="填写笔记标题"
        maxlength="255"
        :disabled="publishing" /></label
    ><label class="field"
      ><span>笔记内容</span
      ><textarea
        v-model="params.content"
        placeholder="分享你的探店体验"
        maxlength="2048"
        :disabled="publishing"
      /></label
    ><button
      class="choose-shop"
      :disabled="publishing"
      @click="showDialog = true"
    >
      <strong>关联商户</strong
      ><span>{{ selectedShop.name || '请选择商户' }}</span
      >›
    </button>
    <p v-if="error" class="inline-error" role="alert">{{ error }}</p>
    <button
      class="primary wide"
      :disabled="!ready || publishing || uploading || deleting.length > 0"
      @click="publish"
    >
      {{ publishing ? '发布中…' : '发布笔记' }}
    </button>
  </section>
  <el-dialog v-model="showDialog" title="选择关联商户"
    ><form class="search-form" @submit.prevent="queryShops">
      <input v-model="shopName" placeholder="搜索商户名称或地点" /><button>
        搜索
      </button>
    </form>
    <div class="shop-picker">
      <button v-for="s in shops" :key="s.id" @click="choose(s)">
        <strong>{{ s.name }}</strong
        ><small>{{ s.area }} · {{ s.address }}</small>
      </button>
    </div>
    <StateBlock
      :loading="shopLoading"
      :error="shopError"
      :empty="!shops.length"
      @retry="queryShops"
  /></el-dialog>
</template>
