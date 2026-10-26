import { defineStore } from 'pinia'
import { ref } from 'vue'
export const useUserStore = defineStore(
  'Hmdp-User',
  () => {
    const token = ref(''),
      userInfo = ref({})
    const setToken = (value) => {
      token.value = value || ''
      userInfo.value = {}
    }
    const clear = () => {
      token.value = ''
      userInfo.value = {}
    }
    return {
      token,
      userInfo,
      setToken,
      clear,
      getToken: () => token.value,
      getUserInfo: () => userInfo.value,
      setUserInfo: (value) => {
        userInfo.value = value || {}
      },
      resetUserInfo: () => {
        userInfo.value = {}
      }
    }
  },
  { persist: { pick: ['token'] } }
)
