<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import request from '@/utils/request'
import { me, image, fallback, upload } from '@/utils/presentation'
import { useUserStore } from '@/stores'
import PageHeader from '@/components/PageHeader.vue'
import StateBlock from '@/components/StateBlock.vue'
const router = useRouter(),
  store = useUserStore(),
  ready = ref(false),
  loading = ref(true),
  saving = ref(false),
  uploading = ref(false),
  error = ref(''),
  fileInput = ref(),
  form = ref({
    nickName: '',
    icon: '',
    introduce: '',
    city: '',
    gender: '',
    birthday: ''
  })
async function load() {
  loading.value = true
  ready.value = false
  error.value = ''
  try {
    const user = await me(),
      data = (await request.get('/user/profile/' + user.id)).data
    form.value = {
      nickName: data.nickName || '',
      icon: data.icon || '',
      introduce: data.introduce || '',
      city: data.city || '',
      gender:
        data.gender === true ? 'true' : data.gender === false ? 'false' : '',
      birthday: data.birthday || ''
    }
    ready.value = true
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
async function avatar(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file || uploading.value) return
  uploading.value = true
  error.value = ''
  try {
    form.value.icon = await upload(file)
  } catch (e) {
    error.value = e.message
  } finally {
    uploading.value = false
  }
}
async function save() {
  if (saving.value || uploading.value) return
  error.value = ''
  if (!form.value.nickName.trim()) {
    error.value = '昵称不能为空'
    return
  }
  saving.value = true
  try {
    await request.put('/user/profile', {
      ...form.value,
      nickName: form.value.nickName.trim(),
      introduce: form.value.introduce.trim(),
      city: form.value.city.trim(),
      gender: form.value.gender === '' ? null : form.value.gender === 'true',
      birthday: form.value.birthday || null
    })
    store.resetUserInfo()
    await router.replace('/InfoHtml')
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}
load()
</script>
<template>
  <PageHeader title="编辑资料" fallback="/InfoHtml" /><StateBlock
    :loading="loading"
    :error="!ready ? error : ''"
    @retry="load"
  />
  <form v-if="ready" class="editor" @submit.prevent="save">
    <div class="avatar-row">
      <img :src="image(form.icon)" alt="头像预览" @error="fallback" /><input
        ref="fileInput"
        class="file-input"
        aria-label="上传头像"
        type="file"
        accept="image/png,image/jpeg,image/webp"
        @change="avatar"
      /><button
        type="button"
        class="secondary"
        :disabled="uploading || saving"
        @click="fileInput.click()"
      >
        {{ uploading ? '上传中…' : '更换头像' }}
      </button>
    </div>
    <label class="field"
      ><span>昵称</span
      ><input
        v-model="form.nickName"
        placeholder="请输入昵称"
        maxlength="32" /></label
    ><label class="field"
      ><span>个人介绍</span
      ><textarea
        v-model="form.introduce"
        placeholder="介绍一下自己"
        maxlength="128"
      /></label
    ><label class="field"
      ><span>城市</span
      ><input
        v-model="form.city"
        placeholder="请输入城市"
        maxlength="64" /></label
    ><label class="field"
      ><span>性别</span
      ><select v-model="form.gender" aria-label="性别">
        <option value="">未设置</option>
        <option value="false">男</option>
        <option value="true">女</option>
      </select></label
    ><label class="field"
      ><span>生日</span
      ><input v-model="form.birthday" type="date" aria-label="生日"
    /></label>
    <p v-if="error" class="inline-error" role="alert">{{ error }}</p>
    <button class="primary wide" :disabled="saving || uploading">
      {{ saving ? '保存中…' : '保存资料' }}
    </button>
  </form>
</template>
