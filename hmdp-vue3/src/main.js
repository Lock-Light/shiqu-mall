import { createApp } from 'vue'
import pinia from '@/stores'
import App from '@/App.vue'
import router from '@/router'
import 'element-plus/dist/index.css'
import '@/assets/css/app.css'
createApp(App).use(pinia).use(router).mount('#app')
