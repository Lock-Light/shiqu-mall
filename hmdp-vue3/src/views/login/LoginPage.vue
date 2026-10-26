<script setup>
import { ref, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'
import { useUserStore } from '@/stores'
import PageHeader from '@/components/PageHeader.vue'
const route = useRoute(),
  router = useRouter(),
  store = useUserStore(),
  phone = ref(''),
  code = ref(''),
  agreed = ref(false),
  sending = ref(false),
  logging = ref(false),
  error = ref(''),
  codeStatus = ref(''),
  remaining = ref(0),
  terms = ref(false)
function tick() {
  remaining.value = Math.max(
    0,
    Math.ceil(
      (Number(sessionStorage.getItem('otp:' + phone.value) || 0) - Date.now()) /
        1000
    )
  )
}
const timer = setInterval(tick, 500)
onUnmounted(() => clearInterval(timer))
function validPhone() {
  if (!/^1[3-9]\d{9}$/.test(phone.value)) {
    error.value =
      '手机号需为11位并以13～19开头。可使用下方体验账号，无需接收短信。'
    return false
  }
  return true
}
function phoneChanged() {
  code.value = ''
  codeStatus.value = ''
  error.value = ''
  tick()
}
async function useDemoAccount() {
  if (sending.value || logging.value) return
  if (phone.value !== '18000000004') {
    phone.value = '18000000004'
    phoneChanged()
  }
  if (remaining.value > 0) {
    codeStatus.value = code.value
      ? '体验账号的验证码已填入，可勾选说明后登录。'
      : '体验账号已填入，请在倒计时结束后重新获取验证码。'
    return
  }
  await send()
}
async function send() {
  if (sending.value || remaining.value || !validPhone()) return
  sending.value = true
  error.value = ''
  codeStatus.value = ''
  const current = phone.value
  try {
    const res = await request.post('/user/code', null, {
      params: { phone: current }
    })
    const received = String(res.data ?? '')
    if (!/^\d{6}$/.test(received))
      throw new Error('未取得有效的演示验证码，请重新获取')
    if (phone.value === current) {
      code.value = received
      codeStatus.value =
        '演示验证码已自动填入，无需接收短信。勾选说明后即可登录。'
    }
    sessionStorage.setItem('otp:' + current, String(Date.now() + 60000))
    tick()
    if (phone.value === current) ElMessage.success('学习演示验证码已填入')
  } catch (e) {
    error.value = e.message
  } finally {
    sending.value = false
  }
}
async function login() {
  if (logging.value || !validPhone()) return
  error.value = ''
  if (!/^\d{6}$/.test(code.value)) {
    error.value = '请输入6位验证码'
    return
  }
  if (!agreed.value) {
    error.value = '请先勾选学习演示说明'
    return
  }
  logging.value = true
  try {
    const { data } = await request.post('/user/login', {
      phone: phone.value,
      code: code.value
    })
    store.setToken(data)
    let target = '/index'
    try {
      const url = new URL(
        String(route.query.redirect || '/index'),
        location.origin
      )
      if (
        url.origin === location.origin &&
        !['/login', '/register'].includes(url.pathname)
      )
        target = url.pathname + url.search + url.hash
    } catch {
      // Invalid browser state falls back to the default view.
    }
    await router.replace(target)
  } catch (e) {
    error.value = e.message
  } finally {
    logging.value = false
  }
}
</script>
<template>
  <PageHeader title="验证码登录" />
  <section class="login-panel">
    <div class="login-brand">
      <img src="/brand/shiqu-mark.svg" alt="" />
      <div>
        <h2>欢迎来到拾趣</h2>
        <p>从喜欢的事开始，发现自己的另一面。</p>
      </div>
    </div>
    <p class="notice">
      学习演示，不发送真实短信。输入有效测试手机号后点击“获取验证码”，随机验证码会自动填入；也可直接使用体验账号。
    </p>
    <button
      type="button"
      class="secondary demo-account"
      :disabled="sending || logging"
      @click="useDemoAccount"
    >
      使用体验账号（18000000004）
    </button>
    <form @submit.prevent="login">
      <label class="field"
        ><span>手机号</span
        ><input
          v-model.trim="phone"
          placeholder="请输入手机号"
          type="tel"
          maxlength="11"
          aria-describedby="phone-help"
          @input="phoneChanged"
          autocomplete="tel" /></label
      ><label class="field"
        ><span>验证码</span>
        <div class="code-row">
          <input
            v-model.trim="code"
            placeholder="请输入验证码"
            inputmode="numeric"
            maxlength="6"
            autocomplete="one-time-code"
          /><button
            type="button"
            :disabled="sending || remaining > 0"
            @click="send"
          >
            {{
              sending
                ? '获取中…'
                : remaining > 0
                  ? remaining + '秒后重发'
                  : '获取验证码'
            }}
          </button>
        </div></label
      >
      <p id="phone-help" class="login-help">
        号码需为11位且以13～19开头，例如18000000004；验证码不是固定的123456。
      </p>
      <p v-if="codeStatus" class="notice" role="status">{{ codeStatus }}</p>
      <div class="agreement">
        <label
          ><input v-model="agreed" type="checkbox" />我已了解学习演示说明</label
        ><button type="button" class="text-button" @click="terms = true">
          查看说明
        </button>
      </div>
      <p v-if="error" class="inline-error" role="alert">{{ error }}</p>
      <button class="primary wide" :disabled="logging">
        {{ logging ? '登录中…' : '登录' }}
      </button>
    </form>
  </section>
  <el-dialog v-model="terms" title="学习演示说明"
    ><p>
      本项目用于课程学习，不发送真实短信。请使用测试手机号。提供模拟付款演示，不产生真实扣款。
    </p>
    <template #footer
      ><button class="primary" @click="terms = false">知道了</button></template
    ></el-dialog
  >
</template>
